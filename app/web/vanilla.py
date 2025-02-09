from app.shared.messages import *
from app.shared.env import *
from app.shared import beanops
from app.pybeansack.models import *
from app.pybeansack.mongosack import LATEST_AND_TRENDING, NEWEST_AND_TRENDING
from app.web.renderer import *
from app.web.custom_ui import *
from nicegui import ui
import inflect

KIND_LABELS = {NEWS: "News", POST: "Posts", BLOG: "Blogs"}
SORT_BY_LABELS = ["Latest", "Trending"]
DEFAULT_SORT_BY = "Latest"

REMOVE_FILTER = "remove-filter"
CONTENT_GRID_CLASSES = "w-full m-0 p-0 grid-cols-1 lg:grid-cols-2 xl:grid-cols-3"
BARISTAS_PANEL_CLASSES = "w-1/4 gt-xs"
TOGGLE_OPTIONS_PROPS = "unelevated rounded no-caps color=dark toggle-color=primary"

sort_by_value = lambda value: LATEST_AND_TRENDING if value == "Trending" else NEWEST_AND_TRENDING

async def render_home(user):
    tags, kind, sort_by = None, DEFAULT_KIND, DEFAULT_SORT_BY # starting default 

    def retrieve_beans(start, limit):
        log("home", user_id=user, tags=tags, kind=kind, sort_by=sort_by, start=start, limit=limit)
        return beanops.get_beans_per_group(tags, kind, None, sort_by_value(sort_by), start, limit)

    def apply_retrieval_filter(filter_tags: list[str] = None, filter_kind: str = None, filter_sort_by: str = None):
        nonlocal tags, kind, sort_by
        if filter_tags:
            tags = filter_tags if filter_tags != REMOVE_FILTER else None
        if filter_kind:
            kind = filter_kind if filter_kind != REMOVE_FILTER else None
        if filter_sort_by:
            sort_by = filter_sort_by
        
        return retrieve_beans
    
    render_banner(HOME_BANNER_TEXT)    
    _render_content(
        user, 
        lambda: beanops.search_tags(query=None, accuracy=None, tags=None, kinds=None, sources=None, last_ndays=2, start=0, limit=MAX_FILTER_TAGS), 
        apply_retrieval_filter
    )   

# async def render_trending_snapshot(user):
#     render_header(user)
#     with ui.grid().classes(CONTENT_GRID_CLASSES):
#         baristas = beanops.get_baristas(user)
#         for barista in baristas:
#             with render_card_container(barista.title, on_click=lambda: navigate_to_barista(barista.id), header_classes="text-wrap bg-dark").classes("bg-transparent"):
#                 if beanops.count_beans(query=None, embedding=barista.embedding, accuracy=barista.accuracy, tags=barista.tags, kinds=None, sources=None, last_ndays=1, limit=1):  
#                     get_beans_func = lambda b=barista: beanops.get_newest_beans(
#                         embedding=b.embedding, 
#                         accuracy=b.accuracy, 
#                         tags=b.tags, 
#                         kinds=None, 
#                         sources=b.sources, 
#                         last_ndays=beanops.MIN_WINDOW, 
#                         start=0, 
#                         limit=beanops.MIN_LIMIT)
#                     render_beans(user, get_beans_func)
#                 else:
#                     render_error_text(NOTHING_TRENDING)                            
#     render_footer()

# async def render_beans_page(user: User, must_have_tags: str|list[str], kind: str = beanops.DEFAULT_KIND): 
#     if must_have_tags:
#         must_have_tags = must_have_tags if isinstance(must_have_tags, list) else [must_have_tags]
#     tags, sort_by = must_have_tags, DEFAULT_SORT_BY # starting default 

#     def get_beans(start, limit):
#         result = beanops.get_trending_beans(embedding=None, accuracy=None, tags=tags, kinds=kind, sources=None, last_ndays=None, start=start, limit=limit) \
#             if sort_by == TRENDING else \
#                 beanops.get_newest_beans(embedding=None, accuracy=None, tags=tags, kinds=kind, sources=None, last_ndays=beanops.MIN_WINDOW, start=start, limit=limit)
#         log("beans_page", user_id=user.email if isinstance(user, User) else None, tags=tags, kind=kind, sort_by=sort_by, start=start, urls=[bean.url for bean in result])
#         return result

#     def trigger_filter(filter_tags: list[str] = None, filter_kind: str = None, filter_sort_by: str = None):
#         nonlocal tags, kind, sort_by
#         if filter_tags == REMOVE_FILTER:
#             tags = must_have_tags
#         else:
#             tags = [must_have_tags, filter_tags] if (must_have_tags and filter_tags) else (must_have_tags or filter_tags) # filter_tags == [] means there is no additional tag to filter with     
#         if filter_kind:
#             kind = filter_kind if filter_kind != REMOVE_FILTER else None
#         if filter_sort_by:
#             sort_by = filter_sort_by
#         return get_beans
    
#     ui.label(tags_banner_text(must_have_tags)).classes("text-h6")
    
#     _render_content(
#         user, 
#         lambda: beanops.get_tags(None, None, None, None, must_have_tags, None, None, None, 0, MAX_FILTER_TAGS), 
#         trigger_filter,
#         initial_kind=kind
#     )

async def render_barista_page(user: User, barista: Barista):    
    tags, kind, sort_by = barista.query_tags, beanops.DEFAULT_KIND, DEFAULT_SORT_BY # starting default values
   
    def retrieve_beans(start, limit):
        log("barista", user_id=user, page_id=barista.id, tags=tags, kinds=kind, sort_by=sort_by, start=start, limit=limit)
        return beanops.get_barista_beans(barista, tags, kind, sort_by_value(sort_by), start, limit)

    def apply_retrieval_filter(filter_tags: list[str] = None, filter_kind: str = None, filter_sort_by: str = None) -> Callable:
        nonlocal tags, kind, sort_by
        if filter_tags:
            tags = [barista.query_tags, filter_tags] if filter_tags != REMOVE_FILTER else barista.query_tags
        if filter_kind:
            kind = filter_kind if filter_kind != REMOVE_FILTER else None
        if filter_sort_by:
            sort_by = filter_sort_by
            
        return retrieve_beans
        
    async def toggle_publish():
        if beanops.db.is_published(barista.id):
            beanops.db.unpublish(barista.id)
            log("unpublished", user_id=beanops.user_id(user), page_id=barista.id)
        else:
            beanops.db.publish(barista.id)
            log("published", user_id=beanops.user_id(user), page_id=barista.id)
            
    async def toggle_follow():
        if barista.id not in user.following:
            beanops.db.follow_barista(user.email, barista.id)
            log("followed", user_id=beanops.user_id(user), page_id=barista.id)
        else:
            beanops.db.unfollow_barista(user.email, barista.id)
            log("unfollowed", user_id=beanops.user_id(user), page_id=barista.id)
            
    with render_banner(barista.title):        
        if isinstance(user, User):
            has_publish_permission = barista.owner == user.email
            has_unfollow_permission = barista.owner != user.email
            with ui.button(icon="more_vert").props("flat").classes("q-ml-md"):
                with ui.menu():  
                    if has_publish_permission:
                        with ui.item("Public"):
                            ui.switch(value=barista.public, on_change=toggle_publish).props("flat checked-icon=public unchecked-icon=public_off")

                    if has_unfollow_permission:
                        with ui.item("Follow"):
                            ui.switch(value=barista.id in user.following, on_change=toggle_follow).props("flat checked-icon=playlist_add_check")

                    # with ui.menu_item("Pour a Filtered Cup", on_click=lambda: ui.notify("Coming soon")):
                    #     ui.avatar(icon="filter_list", color="transparent")
    
    _render_content(
        user, 
        lambda: beanops.get_barista_tags(barista, 0, MAX_FILTER_TAGS), 
        apply_retrieval_filter
    )

def _render_content(user, get_tags_func: Callable, apply_retrieval_filter_func: Callable):
    @ui.refreshable
    def render_beans_panel(filter_tags: list[str] = None, filter_kind: str = None, filter_sort_by: str = None):        
        container = ui.grid().classes(CONTENT_GRID_CLASSES)
        retrieval_func = apply_retrieval_filter_func(filter_tags, filter_kind, filter_sort_by)
        return render_beans_as_extendable_list(user, retrieval_func, container).classes("w-full")

    render_header(user)  

    # tag filter panel
    render_filter_tags(
        load_tags=get_tags_func, 
        on_selection_changed=lambda selected_tags: render_beans_panel.refresh(filter_tags=(selected_tags or REMOVE_FILTER))).classes("w-full")
    
    # kind and sort by filter panel
    with ui.row(wrap=False, align_items="stretch").classes("w-full"):
        ui.toggle(
            options=KIND_LABELS,
            value=DEFAULT_KIND,
            on_change=lambda e: render_beans_panel.refresh(filter_kind=(e.sender.value or REMOVE_FILTER))).props(TOGGLE_OPTIONS_PROPS)
        
        ui.toggle(
            options=SORT_BY_LABELS, 
            value=DEFAULT_SORT_BY, 
            on_change=lambda e: render_beans_panel.refresh(filter_sort_by=e.sender.value)).props("unelevated rounded no-caps color=dark")
    
    render_beans_panel(filter_tags=None, filter_kind=None, filter_sort_by=None)
    render_footer()

async def render_search(user: User, query: str = None, accuracy: float = None, query_tags: str|list[str] = None): 
    tags, kind, last_ndays = query_tags, beanops.DEFAULT_KIND, beanops.DEFAULT_WINDOW

    def retrieve_beans(start, limit):
        log("search", user_id=user, query=query, accuracy=accuracy, tags=tags, kinds=kind, last_ndays=last_ndays, start=start, limit=limit)
        return beanops.search_beans(query, accuracy, tags, kind, None, last_ndays, start, limit)
    
    @ui.refreshable
    def render_result_panel(filter_accuracy: float = None, filter_tags: str|list[str] = None, filter_kind: str = None, filter_last_ndays: int = None):
        nonlocal accuracy, tags, kind, last_ndays        

        if filter_accuracy:
            accuracy = filter_accuracy        
        if filter_tags:
            tags = [filter_tags, query_tags] if filter_tags != REMOVE_FILTER else query_tags
        if filter_kind:    
            kind = filter_kind if filter_kind != REMOVE_FILTER else None
        if filter_last_ndays:
            last_ndays = filter_last_ndays
        
        return render_beans_as_paginated_list(
            user, 
            retrieve_beans, 
            lambda: beanops.count_search_beans(query=query, accuracy=accuracy, tags=tags, kinds=kind, sources=None, last_ndays=last_ndays, limit=beanops.MAX_LIMIT)).classes("w-full")               

    render_header(user)

    trigger_search = lambda: ui.navigate.to(create_search_target(search_input.value))
    with ui.input(placeholder=SEARCH_BEANS_PLACEHOLDER, value=query) \
        .props('rounded outlined input-class=mx-3').classes('w-full self-center lt-sm') \
        .on('keydown.enter', trigger_search) as search_input:
        ui.button(icon="send", on_click=trigger_search).bind_visibility_from(search_input, 'value').props("flat dense")  
    
    # TODO: fill it up with popular searches

    if not (query or query_tags):  return

    with ui.row(wrap=False, align_items="center").classes("w-full justify-between"):    
        # NOTE: temporarily removing the accuracy filter                     
        # with ui.label("Accuracy").classes("w-full"):
        #     accuracy_filter = ui.slider(
        #         min=0.1, max=1.0, step=0.05, 
        #         value=(accuracy or beanops.DEFAULT_ACCURACY), 
        #         on_change=debounce(lambda: render_result_panel.refresh(filter_accuracy=accuracy_filter.value), 1.5)).props("label-always").tooltip("We will be back")

        ui.toggle(
            options=KIND_LABELS, 
            value=beanops.DEFAULT_KIND, 
            on_change=lambda e: render_result_panel.refresh(filter_kind=e.sender.value or REMOVE_FILTER)).props("unelevated rounded no-caps color=dark toggle-color=primary")              

        with ui.label().classes("w-1/2") as last_ndays_label:
            last_ndays_filter = ui.slider(
                min=-30, max=-1, step=1, value=-last_ndays,
                on_change=debounce(lambda: render_result_panel.refresh(filter_last_ndays=-last_ndays_filter.value), 1.5))
            last_ndays_label.bind_text_from(last_ndays_filter, 'value', lambda x: f"Since {naturalday(ndays_ago(-x))}")

    render_filter_tags(
        load_tags=lambda: beanops.search_tags(query=query, accuracy=accuracy, tags=tags, kinds=None, sources=None, last_ndays=last_ndays, start=0, limit=MAX_FILTER_TAGS), 
        on_selection_changed=lambda selected_tags: render_result_panel.refresh(filter_tags=(selected_tags or REMOVE_FILTER))).classes("w-full")
    
    render_result_panel(filter_accuracy=None, filter_tags=None, filter_kind=None, filter_last_ndays=None)
    render_footer()

async def render_registration(userinfo: dict):
    render_header(None)

    async def success():
        beanops.db.create_user(userinfo, beanops.DEFAULT_BARISTAS)
        ui.navigate.to("/")

    with ui.card(align_items="stretch").classes("self-center"):
        ui.label("You look new!").classes("text-h4")
        ui.label("Let's get you signed up.").classes("text-caption")
        
        with ui.row(wrap=False).classes("justify-between"):
            with ui.column(align_items="start"):
                ui.label("User Agreement").classes("text-h6")
                ui.link("What is Espresso", "https://github.com/soumitsalman/espresso/blob/main/README.md", new_tab=True)
                ui.link("Terms of Use", "https://github.com/soumitsalman/espresso/blob/main/docs/terms-of-use.md", new_tab=True)
                ui.link("Privacy Policy", "https://github.com/soumitsalman/espresso/blob/main/docs/privacy-policy.md", new_tab=True)                
            ui.separator().props("vertical")
            with ui.column(align_items="end"):   
                if "picture" in userinfo:
                    ui.image(userinfo["picture"]).classes("w-24")  
                ui.label(userinfo["name"]).classes("text-bold")
                ui.label(userinfo["email"]).classes("text-caption")
        
        agreement = ui.checkbox(text="I have read and understood every single word in each of the links above. I agree to the terms and conditions.") \
            .tooltip("We are legally obligated to ask you this question. Please read the documents to reduce our chances of going to jail.")
        with ui.row():
            ui.button("Agreed", color="primary", icon="thumb_up", on_click=success).bind_enabled_from(agreement, "value").props("unelevated")
            ui.button('Nope!', color="negative", icon="cancel", on_click=lambda: ui.navigate.to("/")).props("outline")

async def render_doc(user: User, doc_id: str):
    render_header(user)
    with open(f"./docs/{doc_id}", 'r') as file:
        ui.markdown(file.read()).classes("w-full md:w-2/3 lg:w-1/2  self-center")
    render_footer()
