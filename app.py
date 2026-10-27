"""쇼핑 리스트 Streamlit 앱 진입점."""

import re
import uuid
from datetime import datetime

import streamlit as st

from storage import MEMO_MAX, NAME_MAX, QTY_MAX, QTY_MIN, load_items_with_warning, update_items

FILTERS = ["전체", "남은 항목", "완료 항목"]
QTY_WARNING = f"수량은 {QTY_MIN}~{QTY_MAX} 사이로 입력해 주세요."

st.set_page_config(page_title="쇼핑 리스트", page_icon="🛒", layout="centered")

if "editing_id" not in st.session_state:
    st.session_state.editing_id = None
if "confirm_clear" not in st.session_state:
    st.session_state.confirm_clear = False
# 추가 폼 수량은 성공 후 콜백에서 1로 되돌리므로, 위젯 value= 대신 세션 상태로 초기값을 준다.
if "add_quantity" not in st.session_state:
    st.session_state.add_quantity = 1


# ---------- 상태 변경 (버튼 콜백) ----------
# 콜백은 화면을 다시 그리기 전에 실행된다. 목록은 세션에 들고 있지 않고 매번 파일에서 읽으며,
# 변경은 update_items로 "최신 목록 읽기 → 이 변경만 적용 → 저장" 해서 다른 탭의 변경을 덮어쓰지 않는다.


def flash(kind: str, message: str, target: str = "add") -> None:
    """다음 렌더링에서 한 번 보여줄 메시지를 남긴다.

    kind: "warning" 또는 "toast". target: "add"(추가 폼 아래) 또는 편집 중인 아이템 id(그 편집 폼 안).
    """
    st.session_state.flash = {"kind": kind, "message": message, "target": target}


def read_fields(name_key: str, qty_key: str, memo_key: str, target: str) -> tuple[str, int, str, bool] | None:
    """입력값을 검증해 (이름, 수량, 메모, 잘렸는지)를 반환한다. 잘못됐으면 경고를 남기고 None."""
    name = st.session_state[name_key].strip()
    if not name:
        flash("warning", "아이템 이름을 입력해 주세요.", target)
        return None
    qty = st.session_state[qty_key]
    if qty is None or not QTY_MIN <= qty <= QTY_MAX:
        flash("warning", QTY_WARNING, target)
        return None
    memo = st.session_state[memo_key].strip()
    truncated = len(name) > NAME_MAX or len(memo) > MEMO_MAX
    return name[:NAME_MAX], int(qty), memo[:MEMO_MAX], truncated


def set_fields(item_id: str, **fields) -> list[dict]:
    def change(items: list[dict]) -> None:
        for item in items:
            if item["id"] == item_id:
                item.update(fields)

    return update_items(change)


def add_item() -> None:
    fields = read_fields("add_name", "add_quantity", "add_memo", "add")
    if not fields:
        return
    name, quantity, memo, truncated = fields
    new_item = {
        "id": str(uuid.uuid4()),
        "name": name,
        "quantity": quantity,
        "memo": memo,
        "checked": False,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    update_items(lambda items: items.append(new_item))
    # 성공했을 때만 입력칸을 비운다. (clear_on_submit을 쓰면 검증에 실패해도 입력이 지워진다.)
    st.session_state.add_name = ""
    st.session_state.add_quantity = 1
    st.session_state.add_memo = ""
    suffix = f" (이름 {NAME_MAX}자·메모 {MEMO_MAX}자까지만 저장)" if truncated else ""
    flash("toast", f"{md_escape(name)} 추가됨{suffix}")


def toggle_item(item_id: str) -> None:
    checked = st.session_state[f"check_{item_id}"]
    items = set_fields(item_id, checked=checked)
    if checked and items and all(i["checked"] for i in items):
        st.session_state.celebrate = True


def start_edit(item_id: str) -> None:
    st.session_state.editing_id = item_id


def save_edit(item_id: str) -> None:
    fields = read_fields(f"edit_name_{item_id}", f"edit_qty_{item_id}", f"edit_memo_{item_id}", item_id)
    if not fields:
        return
    name, quantity, memo, truncated = fields
    set_fields(item_id, name=name, quantity=quantity, memo=memo)
    st.session_state.editing_id = None
    if truncated:
        flash("toast", f"이름 {NAME_MAX}자·메모 {MEMO_MAX}자까지만 저장했어요.")


def cancel_edit() -> None:
    st.session_state.editing_id = None


def delete_item(item_id: str) -> None:
    def change(items: list[dict]) -> None:
        items[:] = [i for i in items if i["id"] != item_id]

    update_items(change)
    if st.session_state.editing_id == item_id:
        st.session_state.editing_id = None


def delete_checked() -> None:
    def change(items: list[dict]) -> None:
        items[:] = [i for i in items if not i["checked"]]

    update_items(change)


def ask_clear() -> None:
    st.session_state.confirm_clear = True


def cancel_clear() -> None:
    st.session_state.confirm_clear = False


def clear_all() -> None:
    update_items(lambda items: items.clear())
    st.session_state.editing_id = None
    st.session_state.confirm_clear = False


# ---------- 표시 도우미 ----------

_MD_SPECIAL = re.compile(r"([\\`*_{}\[\]()#+\-.!|~<>$:])")


def md_escape(text: str) -> str:
    """마크다운으로 렌더링되는 곳(토스트 등)에 넣을 사용자 입력을 이스케이프한다."""
    return _MD_SPECIAL.sub(r"\\\1", text)


# st.markdown(unsafe_allow_html=True)은 HTML 태그 사이의 텍스트도 마크다운으로 해석한다.
# 그래서 HTML 특수문자뿐 아니라 마크다운·이모지(:smile:) 문법 문자도 숫자 엔티티로 바꾼다.
_HTML_SAFE = {ord(c): f"&#{ord(c)};" for c in "&<>\"'\\`*_{}[]()#+-.!|~$:"}


def html_escape(text: str) -> str:
    return text.translate(_HTML_SAFE)


def item_html(item: dict) -> str:
    memo = f'<span class="item-memo">{html_escape(item["memo"])}</span>' if item["memo"] else ""
    done = " done" if item["checked"] else ""
    # 문단(p)으로 감싼다. Streamlit 마크다운 컨테이너가 문단의 아래 여백을 음수 여백으로
    # 상쇄하므로, div로 감싸면 긴 텍스트가 행 아래로 16px 넘친다.
    return (
        f'<p class="item{done}">'
        f'<span class="item-name">{html_escape(item["name"])}</span>'
        f'<span class="item-qty">x{int(item["quantity"])}</span>{memo}</p>'
    )


def show_notice(target: str) -> None:
    if notice and notice["kind"] == "warning" and notice["target"] == target:
        st.warning(notice["message"])


# 커스텀 CSS는 이곳에만 둔다.
st.html(
    """
<style>
.item { line-height: 1.4; overflow-wrap: anywhere; }
.item-name { font-weight: 500; }
.item-qty { margin-left: .4rem; font-size: .85em; opacity: .65; white-space: nowrap; }
.item-memo { margin-left: .4rem; font-size: .8em; opacity: .55; }
.item.done { opacity: .45; }
.item.done .item-name { text-decoration: line-through; }
[class*="st-key-row_"] { border-bottom: 1px solid rgba(128, 128, 128, .2); padding-bottom: .25rem; }
/* 아이템 행: Streamlit 기본 열 최소 폭(128px) 때문에 모바일에서 가로 스크롤이 생기므로,
   체크박스·버튼 열은 내용 크기로, 이름 열이 남은 폭을 모두 쓰게 한다. */
/* wrap=False 행은 overflow:auto라 문단 여백 몇 px 때문에 세로 스크롤바가 생긴다. 열 최소 폭을 없앴으니 스크롤이 필요 없다. */
[class*="st-key-row_"] [data-testid="stHorizontalBlock"] { gap: .25rem; overflow: visible; }
[class*="st-key-row_"] [data-testid="stColumn"] { min-width: 0 !important; width: auto !important; flex: 0 0 auto !important; }
[class*="st-key-row_"] [data-testid="stColumn"]:nth-child(2) { flex: 1 1 auto !important; }
/* 수정·삭제 아이콘 버튼은 손가락으로 누르기 쉽게 40px 정사각형 이상으로 */
[class*="st-key-edit_"] button, [class*="st-key-del_"] button { min-width: 2.5rem; min-height: 2.5rem; }
/* 좁은 화면에서 제목이 두 줄로 쪼개지지 않게 */
h1 { font-size: clamp(1.9rem, 9vw, 2.75rem) !important; white-space: nowrap; }
</style>
"""
)


# ---------- 화면 ----------

# 매 실행마다 파일에서 읽으므로 다른 탭에서 바꾼 내용도 다음 조작 때 바로 보인다.
items, storage_warning = load_items_with_warning()
item_ids = {i["id"] for i in items}
done = sum(1 for i in items if i["checked"])
total = len(items)
notice = st.session_state.pop("flash", None)

# 다른 탭에서 지워졌거나 목록이 비면 남아 있는 편집·전체 삭제 상태를 정리한다.
if st.session_state.editing_id not in item_ids:
    st.session_state.editing_id = None
if total == 0:
    st.session_state.confirm_clear = False

st.title("🛒 쇼핑 리스트")
if storage_warning:
    st.error(storage_warning)

# 진행률
st.progress(done / total if total else 0.0, text=f"{done} / {total} 완료")
if total and done == total:
    st.success("모두 담았어요! 장보기 완료 🎉")
if st.session_state.pop("celebrate", False):
    st.balloons()

# 아이템 입력 폼
# max_chars를 두면 제한보다 긴 글을 붙여넣을 때 입력칸이 통째로 비워지므로, 길이는 저장할 때 자른다.
# 수량 min/max도 위젯에 두면 영어 툴팁으로만 안내되므로 저장할 때 검사해 한글로 안내한다.
with st.form("add_form"):
    name_col, qty_col = st.columns([5, 2], wrap=False, vertical_alignment="bottom")
    name_col.text_input("아이템 이름", key="add_name", placeholder="예: 우유")
    qty_col.number_input("수량", key="add_quantity", step=1)
    st.text_input("메모 (선택)", key="add_memo", placeholder="예: 저지방")
    st.form_submit_button("추가", type="primary", icon=":material/add:", width="stretch", on_click=add_item)

show_notice("add")
if notice and notice["kind"] == "toast":
    st.toast(notice["message"], icon="🛒")

# 필터 / 정렬
with st.container(horizontal=True, vertical_alignment="center", gap="medium"):
    view = st.segmented_control(
        "필터", FILTERS, key="filter", default="전체", required=True, label_visibility="collapsed"
    )
    checked_last = st.toggle("완료 항목 아래로", key="checked_last")

visible = items
if view == "남은 항목":
    visible = [i for i in items if not i["checked"]]
elif view == "완료 항목":
    visible = [i for i in items if i["checked"]]
if checked_last:
    visible = sorted(visible, key=lambda i: i["checked"])  # 안정 정렬이라 추가 순서 유지

# 아이템 목록
if not items:
    st.info("리스트가 비어 있어요.")
elif not visible:
    st.info("해당하는 항목이 없어요.")

for item in visible:
    item_id = item["id"]
    if st.session_state.editing_id == item_id:
        with st.form(f"edit_form_{item_id}"):
            name_col, qty_col = st.columns([5, 2], wrap=False, vertical_alignment="bottom")
            name_col.text_input("이름", value=item["name"], key=f"edit_name_{item_id}")
            qty_col.number_input("수량", value=item["quantity"], key=f"edit_qty_{item_id}", step=1)
            st.text_input("메모", value=item["memo"], key=f"edit_memo_{item_id}")
            show_notice(item_id)
            with st.container(horizontal=True):
                st.form_submit_button("저장", type="primary", on_click=save_edit, args=(item_id,))
                st.form_submit_button("취소", on_click=cancel_edit)
        continue

    # 체크 상태는 파일이 기준이다. 다른 탭에서 바뀌었을 수 있으므로 위젯을 만들기 전에 맞춘다.
    st.session_state[f"check_{item_id}"] = item["checked"]
    with st.container(key=f"row_{item_id}"):
        # wrap=False: 좁은 화면에서도 열이 세로로 쪼개지지 않고 한 줄을 유지한다.
        check_col, label_col, edit_col, del_col = st.columns(
            [1, 9, 1, 1], gap="small", vertical_alignment="center", wrap=False
        )
        check_col.checkbox(
            item["name"],
            key=f"check_{item_id}",
            on_change=toggle_item,
            args=(item_id,),
            label_visibility="collapsed",
        )
        label_col.markdown(item_html(item), unsafe_allow_html=True)
        edit_col.button("✏️", key=f"edit_{item_id}", help="수정", type="tertiary", on_click=start_edit, args=(item_id,))
        del_col.button("🗑️", key=f"del_{item_id}", help="삭제", type="tertiary", on_click=delete_item, args=(item_id,))

st.divider()

# 하단 일괄 작업
with st.container(horizontal=True):
    st.button("체크된 항목 삭제", icon=":material/done_all:", on_click=delete_checked, disabled=done == 0)
    st.button("전체 삭제", icon=":material/delete_sweep:", on_click=ask_clear, disabled=total == 0)

if st.session_state.confirm_clear:
    st.warning(f"아이템 {total}개를 모두 삭제할까요? 되돌릴 수 없어요.")
    with st.container(horizontal=True):
        st.button("네, 모두 삭제", type="primary", on_click=clear_all)
        st.button("취소", key="cancel_clear", on_click=cancel_clear)
