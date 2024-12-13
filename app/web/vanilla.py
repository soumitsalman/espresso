from itertools import chain
from app.shared.utils import *
from app.shared.messages import *
from app.shared.espressops import *
from app.shared.beanops import *
from app.pybeansack.datamodels import *
from app.pybeansack.utils import ndays_ago
from nicegui import ui
from icecream import ic
from app.web.renderer import *

KIND_LABELS = {NEWS: "News", POST: "Posts", BLOG: "Blogs"}
TRENDING, LATEST = "Trending", "Latest"
DEFAULT_SORT_BY = LATEST
SORT_BY_LABELS = {LATEST: LATEST, TRENDING: TRENDING}

REMOVE_FILTER = "remove-filter"
CONTENT_GRID_CLASSES = "w-full grid-cols-1 md:grid-cols-2 lg:grid-cols-3"
BARISTAS_PANEL_CLASSES = "w-1/4 gt-xs"
TOGGLE_OPTIONS_PROPS = "unelevated rounded no-caps color=dark toggle-color=primary"

async def render_home(user):
    render_header(user)
    with ui.row(wrap=False).classes("w-full"): 
        render_baristas_panel(user).classes(BARISTAS_PANEL_CLASSES)
        with ui.grid().classes(CONTENT_GRID_CLASSES):
            # render trending blogs, posts and news
            for id, label in KIND_LABELS.items():
                with render_card_container(label, header_classes="text-h6 bg-dark").classes("bg-transparent"):
                    # TODO: add a condition with count_beans to check if there are any beans. If not, then render a label with NOTHING TRENDING
                    render_beans(user, lambda kind_id=id: beanops.get_trending_beans(tags=None, kinds=kind_id, sources=None, last_ndays=1, start=0, limit=MAX_ITEMS_PER_PAGE)) \
                        if beanops.count_beans(query=None, accuracy=None, tags=None, kinds=id, sources=None, last_ndays=1, limit=1) else \
                            render_error_text(NOTHING_TRENDING)
            # render trending pages
            with render_card_container("Explore"):                
                render_barista_names(user, espressops.db.sample_baristas(5))
    render_footer()

async def render_trending_snapshot(user):
    baristas = espressops.db.get_baristas(user.following if user else espressops.DEFAULT_BARISTAS)

    render_header(user)
    with ui.row(wrap=False).classes("w-full"): 
        render_baristas_panel(user).classes(BARISTAS_PANEL_CLASSES)
        with ui.column(align_items="stretch").classes("w-full m-0 p-0"):
            for barista in baristas:
                with render_card_container(barista.title, on_click=create_barista_route(barista), header_classes="text-wrap bg-dark").classes("bg-transparent"):
                    if beanops.count_beans(query=None, accuracy=None, tags=barista.tags, kinds=None, sources=None, last_ndays=1, limit=1):  
                        get_beans_func = lambda barista=barista: list(chain(*[
                            beanops.get_newest_beans(tags=barista.tags, kinds=kind, sources=barista.sources, last_ndays=MIN_WINDOW, start=0, limit=MIN_LIMIT) \
                            for kind in KIND_LABELS.keys()
                        ]))
                        render_beans(user, get_beans_func, ui.grid().classes(CONTENT_GRID_CLASSES))
                        pass
                    else:
                        render_error_text(NOTHING_TRENDING)                            
    render_footer()

def tags_banner_text(tags: str|list[str], kind: str = None):
    tag_label = None
    if tags:
        tag_label = ", ".join(tags) if isinstance(tags, list) else tags
    return f"{KIND_LABELS[kind]} on {tag_label}" if kind and tags else (KIND_LABELS[kind] or tag_label)

async def render_beans_page(user: User, must_have_tags: str|list[str], kind: str = DEFAULT_KIND): 
    # must_have_tags = must_have_tags if isinstance(must_have_tags, list) else [must_have_tags]
    tags, sort_by = must_have_tags, DEFAULT_SORT_BY # starting default 

    def trigger_filter(filter_tags: list[str] = None, filter_kind: str = None, filter_sort_by: str = None):
        nonlocal tags, kind, sort_by
        if filter_tags == REMOVE_FILTER:
            tags = must_have_tags
        else:
            tags = [must_have_tags, filter_tags] if (must_have_tags and filter_tags) else (must_have_tags or filter_tags) # filter_tags == [] means there is no additional tag to filter with
        
        if filter_kind:
            kind = filter_kind if filter_kind != REMOVE_FILTER else None
        if filter_sort_by:
            sort_by = filter_sort_by

        return lambda start, limit: \
            beanops.get_trending_beans(tags=tags, kinds=kind, sources=None, last_ndays=None, start=start, limit=limit) \
                if sort_by == TRENDING else \
                    beanops.get_newest_beans(tags=tags, kinds=kind, sources=None, last_ndays=MIN_WINDOW, start=start, limit=limit)
    
    render_page(
        user, 
        tags_banner_text(must_have_tags, kind), 
        lambda: beanops.get_tags(must_have_tags, None, None, None, 0, DEFAULT_LIMIT), 
        trigger_filter)

async def render_barista_page(user: User, barista: Barista):    
    tags, kind, sort_by = barista.tags, DEFAULT_KIND, DEFAULT_SORT_BY # starting default values
    
    def trigger_filter(filter_tags: list[str] = None, filter_kind: str = None, filter_sort_by: str = None):
        nonlocal tags, kind, sort_by
        if filter_tags: # explicitly mentioning is not None is important because that is the default value
            tags = [barista.tags, filter_tags] if filter_tags != REMOVE_FILTER else barista.tags # filter_tags == [] means there is no additional tag to filter with
        if filter_kind:
            kind = filter_kind if filter_kind != REMOVE_FILTER else None
        if filter_sort_by:
            sort_by = filter_sort_by

        return lambda start, limit: \
            beanops.get_trending_beans(tags=tags, kinds=kind, sources=barista.sources, last_ndays=barista.last_ndays, start=start, limit=limit) \
                if sort_by == TRENDING else \
                    beanops.get_newest_beans(tags=tags, kinds=kind, sources=barista.sources, last_ndays=MIN_WINDOW, start=start, limit=limit)

    render_page(
        user, 
        barista.title, 
        lambda: beanops.get_tags(barista.tags, None, None, None, 0, DEFAULT_LIMIT), 
        trigger_filter)

def render_page(user, page_title: str, get_filter_tags_func: Callable, trigger_filter_func: Callable, initial_kind: str = DEFAULT_KIND):
    @ui.refreshable
    def render_beans_panel(filter_tags: list[str] = None, filter_kind: str = None, filter_sort_by: str = None):        
        return render_beans_as_extendable_list(
            user, 
            trigger_filter_func(filter_tags, filter_kind, filter_sort_by), 
            ui.grid().classes(CONTENT_GRID_CLASSES)
        ).classes("w-full")

    render_header(user)  
    with ui.row(wrap=False).classes("w-full"): 
        render_baristas_panel(user).classes(BARISTAS_PANEL_CLASSES)
        with ui.column(align_items="stretch").classes("w-full m-0 p-0"):  
            with ui.row(wrap=False, align_items="start").classes("q-mb-md w-full"):
                ui.label(page_title).classes("text-h4 banner")
                # if user:
                #     ui.button("Follow", icon="add").props("unelevated")

            render_filter_tags(
                load_tags=get_filter_tags_func, 
                on_selection_changed=lambda selected_tags: render_beans_panel.refresh(filter_tags=(selected_tags or REMOVE_FILTER)))
            
            with ui.row(wrap=False, align_items="stretch"):
                ui.toggle(
                    options=KIND_LABELS,
                    value=DEFAULT_KIND,
                    on_change=lambda e: render_beans_panel.refresh(filter_kind=(e.sender.value or REMOVE_FILTER))).props(TOGGLE_OPTIONS_PROPS)
                
                ui.toggle(
                    options=SORT_BY_LABELS, 
                    value=DEFAULT_SORT_BY, 
                    on_change=lambda e: render_beans_panel.refresh(filter_sort_by=e.sender.value)).props("unelevated rounded no-caps color=dark")
            render_beans_panel(filter_tags=None, filter_kind=None, filter_sort_by=None).classes("w-full")
    render_footer()

SAVED_PAGE = "saved_page"
SEARCH_PAGE_TABS = {**KIND_LABELS, **{SAVED_PAGE: "Pages"}}
# NOTE: if query length is small think of it as a domain/genre
prep_query = lambda query: f"Domain / Genre / Category / Topic: {query}" if len(query.split()) > 3 else query
async def render_search(user: User, query: str, accuracy: float):
    tags, kind, last_ndays = None, DEFAULT_KIND, DEFAULT_WINDOW
    # this is different from others
    # need to maintain a list of selected_tags.
    # if search is done by a tag then filtering by tag should take into account must presence of the search tag and then or relationship of the selected_tags
    # filtering by bean kind and slider should take into account the selected tags
    @ui.refreshable
    def render_result_panel(filter_accuracy: float = None, filter_tags: str|list[str] = None, filter_kind: str = None, filter_last_ndays: int = None):
        nonlocal accuracy, tags, kind, last_ndays        

        if filter_accuracy:
            accuracy = filter_accuracy        
        if filter_tags:
            tags = filter_tags if filter_tags != REMOVE_FILTER else None
        if filter_kind:    
            kind = filter_kind if filter_kind != REMOVE_FILTER else None
        if filter_last_ndays:
            last_ndays = filter_last_ndays

        if kind == SAVED_PAGE:
            result = espressops.search_baristas(query) if query else None
            return render_barista_names(user, result) \
                if result else \
                    render_error_text(NOTHING_FOUND)
        
        return render_paginated_beans(
            user, 
            lambda start, limit: beanops.vector_search_beans(query=prep_query(query), accuracy=accuracy, tags=tags, kinds=kind, sources=None, last_ndays=last_ndays, start=start, limit=limit), 
            lambda: beanops.count_beans(query=query, accuracy=accuracy, tags=tags, kinds=kind, sources=None, last_ndays=last_ndays, limit=MAX_LIMIT))                

    render_header(user)
    with ui.row(wrap=False).classes("w-full"):
        render_baristas_panel(user).classes(BARISTAS_PANEL_CLASSES)
        with ui.column(align_items="stretch").classes("w-full m-0 p-0"):

            trigger_search = lambda: ui.navigate.to(create_search_target(search_input.value))
            with ui.input(placeholder=SEARCH_PLACEHOLDER, value=query) \
                .props('rounded outlined input-class=mx-3').classes('w-full self-center lt-sm') \
                .on('keydown.enter', trigger_search) as search_input:
                ui.button(icon="send", on_click=trigger_search).bind_visibility_from(search_input, 'value').props("flat dense")  

            if query:             
                with ui.grid(columns=2).classes("w-full"):                         
                    with ui.label("Accuracy").classes("w-full"):
                        accuracy_filter = ui.slider(
                            min=0.1, max=1.0, step=0.05, 
                            value=(accuracy or DEFAULT_ACCURACY), 
                            on_change=debounce(lambda: render_result_panel.refresh(filter_accuracy=accuracy_filter.value), 1.5)).props("label-always")

                    with ui.label().classes("w-full") as last_ndays_label:
                        last_ndays_filter = ui.slider(
                            min=-30, max=-1, step=1, value=-last_ndays,
                            on_change=debounce(lambda: render_result_panel.refresh(filter_last_ndays=-last_ndays_filter.value), 1.5))
                        last_ndays_label.bind_text_from(last_ndays_filter, 'value', lambda x: f"Since {naturalday(ndays_ago(-x))}")

                kind_filter = ui.toggle(
                    options=SEARCH_PAGE_TABS, 
                    value=DEFAULT_KIND, 
                    on_change=lambda: render_result_panel.refresh(filter_kind=kind_filter.value or REMOVE_FILTER)).props("unelevated rounded no-caps color=dark toggle-color=primary").classes("w-full")               
                
                render_result_panel(filter_accuracy=None, filter_tags=None, filter_kind=None, filter_last_ndays=None).classes("w-full")
            # TODO: fill it up with popular searches
    render_footer()

async def render_registration(userinfo: dict):
    render_header(None)

    async def success():
        espressops.db.create_user(userinfo)
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