from app.shared.consts import *
from app.shared.env import *
from app.web import beanops
from pybeansack.models import *
from app.web.context import *
from app.web.renderer import *
from app.web.custom_ui import *
from nicegui import ui

from pybeansack.mongosack import TRENDING, LATEST

BARISTAS_PANEL_CLASSES = "w-1/4 gt-xs"
MAINTAIN_VALUE = "__MAINTAIN_VALUE__"

async def render_beans_for_home(context: Context):
    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.get_beans_for_home(context.kind, context.tags, None, config.filters.page.default_window, context.sort_by, start, limit)
    
    def apply_filter(context: Context, filter_item: str|list[str] = MAINTAIN_VALUE):
        if filter_item is not MAINTAIN_VALUE:
            context.tags = filter_item
        return context
    
    render_banner(HOME_BANNER_TEXT)    
    render_page_contents(
        context, 
        retrieve_beans,
        get_filter_tags=lambda: beanops.search_filter_tags(query=None, accuracy=None, tags=None, sources=None, last_ndays=config.filters.page.default_window, start=0, limit=config.filters.page.max_tags),
        apply_filter_func=apply_filter
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

async def render_beans_for_barista(context: Context):  
    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.get_beans_for_page(context.page, context.kind, context.tags, context.sort_by, start, limit)
        
    def get_filters_items():
        if context.page.query_embedding: return beanops.get_filter_tags_for_page(context.page, 0, config.filters.max_tags)
        else: return config.filters.page.categories

    def apply_filter(context: Context, filter_item: str|list[str] = MAINTAIN_VALUE):
        if filter_item is not MAINTAIN_VALUE: context.tags = filter_item
        return context
            
    render_page_banner(context)
    render_page_contents(context, retrieve_beans, get_filters_items, apply_filter)

async def render_beans_for_source(context: Context):
    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.get_beans_for_source(context.sources, context.kind, context.tags, None, context.sort_by, start, limit)

    def apply_filter(context: Context, filter_item: str|list[str] = MAINTAIN_VALUE):
        if filter_item is not MAINTAIN_VALUE: context.tags = filter_item
        return context
    
    render_banner(context.sources)
    render_page_contents(context, retrieve_beans, lambda: config.filters.page.categories, apply_filter)

# async def render_custom_page(context: Context): 
#     initial_tags = context.tags
#     use_topic_filter = bool(context.sources)

#     def retrieve_beans(start, limit):
#         context.log("retrieve", start=start, limit=limit)
#         return beanops.search_beans(query=None, accuracy=None, tags=context.tags, kinds=context.kind, sources=context.sources, last_ndays=None, sort_by=context.sort_by, start=start, limit=limit)
        
#     def get_filters_items():
#         if use_topic_filter: return {b.id: b.title for b in beanops.get_baristas(DEFAULT_TOPIC_FILTERS, beanops.BARISTA_MINIMAL_FIELDS)}
#         else: return beanops.search_tags(None, None, context.tags, None, context.sources, None, 0, MAX_FILTER_TAGS)

#     def apply_filter(context: Context, filter_item: str|list[str] = MAINTAIN_VALUE):
#         if filter_item is not MAINTAIN_VALUE:
#             if use_topic_filter: context.topic = filter_item
#             else: context.tags = [initial_tags, filter_item] if (initial_tags and filter_item) else (initial_tags or filter_item)
#         return context
    
#     render_banner(context.tags or context.sources)
#     render_barista_contents(context, retrieve_beans, get_filters_items, apply_filter)

# def render_content(context: Context, get_tags_func: Callable, apply_filter_func: Callable, retrieval_func: Callable):
#     def apply_filter(**kwargs):
#         apply_filter_func(**kwargs)
#         render_beans_panel.refresh()

#     @ui.refreshable
#     def render_beans_panel():                
#         return render_beans_as_extendable_list(
#             context, 
#             retrieval_func, 
#             ui.grid().classes(CONTENT_GRID_CLASSES)).classes("w-full")

#     render_header(context)  
        
#     # kind and sort by filter panel
#     with ui.row(wrap=False, align_items="stretch").classes("w-full"):
#         ui.toggle(
#             options=KIND_LABELS,
#             value=DEFAULT_KIND,
#             on_change=lambda e: apply_filter(filter_kind=e.sender.value)).props(TOGGLE_OPTIONS_PROPS+" clearable")
#         ui.toggle(
#             options=list(beanops.SORT_BY.keys()), 
#             value=DEFAULT_SORT_BY, 
#             on_change=lambda e: apply_filter(filter_sort_by=e.sender.value)).props(TOGGLE_OPTIONS_PROPS)
    
#     # tag filter panel
#     render_filter_tags(
#         load_tags=get_tags_func, 
#         on_selection_changed=lambda selected_tags: apply_filter(filter_tags=selected_tags)).classes("w-full")
#     render_beans_panel()
#     render_related_baristas(context)
#     render_footer()

def render_page_contents(
    context: Context, 
    retrieve_beans_func: Callable, 
    get_filter_tags: Callable = None,
    apply_filter_func: Callable = None
):
    context.kind, context.sort_by = config.filters.page.default_kind, SORT_BY_OPTIONS[config.filters.page.default_sort_by] # starting default values

    @ui.refreshable
    def render_beans_panel(ctx: Context):     
        # container = ui.row(wrap=True, align_items = "start").classes(STRETCH_FIT)           
        return render_beans_as_extendable_list(ctx, retrieve_beans_func).classes("w-full")
    
    def apply_filter(
        filter_kind: str = MAINTAIN_VALUE,  
        filter_sort_by: str = MAINTAIN_VALUE,
        **kwargs
    ):
        nonlocal context
        if filter_kind is not MAINTAIN_VALUE:    
            context.kind = filter_kind
        if filter_sort_by is not MAINTAIN_VALUE:
            context.sort_by = filter_sort_by
        if kwargs:
            context = apply_filter_func(context, **kwargs)
        render_beans_panel.refresh(context)

    render_header(context)  
    # kind and sort by filter panel
    with ui.row(wrap=False, align_items="stretch").classes("w-full"):
        render_kind_filters(context, lambda kind: apply_filter(filter_kind=kind))
        render_sort_by_filters(context, lambda sort_by: apply_filter(filter_sort_by=sort_by))

    # topic filter panel
    if get_filter_tags:
        render_tag_filters(
            context,
            load_items=get_filter_tags, 
            on_selection_changed=lambda selected_item: apply_filter(filter_item=selected_item)
        ).classes("w-full")

    render_beans_panel(context)
    render_similar_channels(context)
    render_footer()

async def render_search(context: Context): 
    initial_tags, context.kind = context.tags, config.filters.bean.default_kind

    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.search_beans(context.query, context.accuracy, context.tags, context.kind, context.sources, context.last_ndays, None, start, limit)
    
    @ui.refreshable
    def render_search_result():
        return render_beans_as_paginated_list(
            context, 
            retrieve_beans, 
            lambda: beanops.count_search_beans(context.query, context.accuracy, context.tags, context.kind, context.sources, context.last_ndays, beanops.MAX_LIMIT)).classes("w-full")               

    def apply_filter(
        filter_kind: str = MAINTAIN_VALUE, 
        filter_tags: str|list[str] = MAINTAIN_VALUE
    ):
        if filter_kind is not MAINTAIN_VALUE:    
            context.kind = filter_kind
        if filter_tags is not MAINTAIN_VALUE:
            context.tags = [initial_tags, filter_tags] if (initial_tags and filter_tags) else (initial_tags or filter_tags)
        return render_search_result.refresh()
    
    render_header(context)
    render_search_controls(context).classes("w-full")
    
    if context.query or context.tags:
        render_kind_filters(lambda e: apply_filter(filter_kind=e.sender.value))
         
        # render_filter_items(
        #     load_items=lambda: beanops.search_tags(query=context.query, accuracy=context.accuracy, tags=context.tags, kinds=context.kind, sources=context.sources, last_ndays=context.last_ndays, start=0, limit=MAX_FILTER_TAGS), 
        #     on_selection_changed=lambda selected_tags: apply_filter(filter_tags=selected_tags)
        # ).classes("w-full")
        render_search_result()
    
    render_footer()

async def render_registration(context: Context):
    userinfo = context.user

    async def success():
        beanops.db.create_user(userinfo, config.filters.page.default_channels)
        context.log("registered")
        ui.navigate.to("/")

    async def cancel():
        context.log("cancelled")
        ui.navigate.to("/")
        
    context.log("registering")

    render_header(context)    
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
            ui.button('Nope!', color="negative", icon="cancel", on_click=cancel).props("outline")
    render_footer()

async def render_doc(user: User, doc_id: str):
    render_header(user)
    with open(f"./docs/{doc_id}", 'r') as file:
        ui.markdown(file.read()).classes("w-full md:w-2/3 lg:w-1/2  self-center")
    render_footer()

KIND_OPTIONS = {NEWS: "News", BLOG: "Blogs", POST: "Posts"}
def render_kind_filters(context: Context, on_change):
    return ui.toggle(
        options={k:v for k,v in KIND_OPTIONS.items() if k in config.filters.page.kinds}, 
        value=config.filters.page.default_kind, 
        on_change=lambda e: on_change(e.sender.value)
    ).props(TOGGLE_OPTIONS_PROPS+" clearable") 

SORT_BY_OPTIONS = {"Latest": LATEST, "Trending": TRENDING}
def render_sort_by_filters(context: Context, on_change):
    return ui.toggle(
        options=list(SORT_BY_OPTIONS.keys()), 
        value=config.filters.page.default_sort_by, 
        on_change=lambda e: on_change(SORT_BY_OPTIONS[e.sender.value])
    ).props(TOGGLE_OPTIONS_PROPS)