from app.shared.consts import *
from app.shared.env import *
from app.web import beanops
from app.pybeansack.models import *
from app.web.context import *
from app.web.renderer import *
from app.web.custom_ui import *
from nicegui import ui

from app.pybeansack.mongosack import TRENDING, LATEST

BARISTAS_PANEL_CLASSES = "w-1/4 gt-xs"
MAINTAIN_VALUE = "__MAINTAIN_VALUE__"

async def render_home(context: Context):
    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.get_beans_for_home(context.kind, context.tags, None, config.filters.page.default_window, context.sort_by, start, limit)
    
    def apply_filter(context: Context, filter_item: str|list[str] = MAINTAIN_VALUE):
        if filter_item is not MAINTAIN_VALUE: context.tags = filter_item
        return context
    
    render_banner(HOME_BANNER_TEXT)   
    _render_generated_beans_panel(context)
    render_page_contents(
        context, 
        retrieve_beans,
        get_filter_tags=lambda: beanops.get_filter_tags_for_custom_page(tags=None, sources=None, last_ndays=config.filters.page.default_window, start=0, limit=config.filters.page.max_tags),
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

async def render_stored_page(context: Context):  
    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.get_beans_for_stored_page(context.page, context.kind, context.tags, config.filters.page.default_window, context.sort_by, start, limit)
        
    def get_filters_items():
        if context.page.query_embedding: return beanops.get_filter_tags_for_stored_page(context.page, config.filters.page.default_window, 0, config.filters.page.max_tags)
        else: return config.filters.page.categories

    def apply_filter(context: Context, filter_item: str|list[str] = MAINTAIN_VALUE):
        if filter_item is not MAINTAIN_VALUE: context.tags = filter_item
        return context
            
    render_page_banner(context)
    _render_generated_beans_panel(context)
    render_page_contents(context, retrieve_beans, get_filters_items, apply_filter)

async def render_custom_page(context: Context): 
    initial_tags = context.tags

    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.get_beans_for_custom_page(context.kind, tags=context.tags, sources=context.sources, last_ndays=config.filters.page.default_window, sort_by=context.sort_by, start=start, limit=limit)
        
    def get_filters_items():
        if context.page_type in [K_SOURCE, K_ENTITIES]: return config.filters.page.categories
        else: return beanops.get_filter_tags_for_custom_page(initial_tags, context.sources, config.filters.page.default_window, 0, config.filters.page.max_tags)

    def apply_filter(context: Context, filter_item: str|list[str] = MAINTAIN_VALUE):
        if filter_item is not MAINTAIN_VALUE:
            context.tags = [initial_tags, filter_item] if (initial_tags and filter_item) else (initial_tags or filter_item)
        return context
    
    render_page_banner(context)
    _render_generated_beans_panel(context)
    render_page_contents(context, retrieve_beans, get_filters_items, apply_filter)

async def render_related_beans_page(context: Context):
    initial_tags = context.tags

    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.get_related_beans(context.page.url, context.kind, tags=context.tags, sources=context.sources, last_ndays=config.filters.page.default_window, sort_by=context.sort_by, start=start, limit=limit)
        
    get_filters_items = lambda: random.sample(context.page.entities, min(len(context.page.entities), config.filters.page.max_tags)) if context.page.entities else None

    def apply_filter(context: Context, filter_item: str|list[str] = MAINTAIN_VALUE):
        if filter_item is not MAINTAIN_VALUE:
            context.tags = [initial_tags, filter_item] if (initial_tags and filter_item) else (initial_tags or filter_item)
        return context
    
    render_page_banner(context)
    render_page_contents(context, retrieve_beans, get_filters_items, apply_filter)

async def render_generated_bean_page(context: Context):
    bean = context.page

    render_header(context)  
    with render_banner(bean.title):
        render_entity_as_chip("AI Generated", False).classes("q-mx-sm")
    ui.markdown("\n".join(["> "+v for v in bean.verdict]))    
    ui.markdown("\n".join(bean.analysis))
    ui.label("Insights & Datapoints").classes("text-bold")
    ui.markdown("\n".join(bean.insights))
    if bean.entities: render_bean_entities(context, bean)
    #     with ui.row(wrap=True, align_items="baseline").classes("gap-1 text-caption"):
    #         list(map(render_entity_as_link, bean.entities))

    render_thick_separator()

    # now render related items
    def retrieve_related_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.get_related_beans(bean.url, context.kind, tags=context.tags, sources=context.sources, last_ndays=config.filters.page.default_window, sort_by=context.sort_by, start=start, limit=limit)
    render_page_contents(context, retrieve_related_beans, None, None)

def _render_generated_beans_panel(context: Context):
    page = context.page if context.is_stored_page else None
    if not beanops.count_generated_beans(page, tags=context.tags, last_ndays=config.filters.page.default_window, limit=1): return
    render_beans(
        context,
        lambda: beanops.get_generated_beans(page, tags=context.tags, last_ndays=config.filters.page.default_window, start=0, limit=config.filters.page.max_beans),
        render_grid()
    )
    render_thick_separator()

def render_page_contents(
    context: Context, 
    retrieve_beans_func: Callable, 
    get_filter_tags: Callable = None,
    apply_filter_func: Callable = None
):
    context.kind, context.sort_by = config.filters.page.default_kind, SORT_BY_OPTIONS[config.filters.page.default_sort_by] # starting default values

    @ui.refreshable
    def render_beans_panel(ctx: Context):     
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
    with ui.row(wrap=False, align_items="stretch").classes("w-full justify-between md:justify-start"):
        render_kind_filters(context, lambda kind: apply_filter(filter_kind=kind))
        render_sort_by_filters(context, lambda sort_by: apply_filter(filter_sort_by=sort_by))

    # topic filter panel
    if get_filter_tags: render_filter_tags(
        context,
        load_items=get_filter_tags, 
        on_selection_changed=lambda selected_item: apply_filter(filter_item=selected_item)
    ).classes("w-full")

    render_beans_panel(context)
    render_similar_pages(context)
    render_footer()

async def render_search(context: Context): 
    initial_tags, context.kind = context.tags, config.filters.page.default_kind

    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.search_beans(context.query, context.accuracy, context.kind, context.tags, context.sources, context.last_ndays, start, limit)
    
    @ui.refreshable
    def render_search_result():
        return render_beans_as_paginated_list(
            context, 
            retrieve_beans, 
            lambda: beanops.count_search_beans(context.query, context.accuracy, context.kind, context.tags, context.sources, context.last_ndays, beanops.MAX_LIMIT)).classes("w-full")               

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
    
    if context.query:
        render_kind_filters(context, lambda kind: apply_filter(filter_kind=kind))
         
        render_filter_tags(
            context,
            load_items=lambda: beanops.search_filter_tags(query=context.query, accuracy=context.accuracy, tags=context.tags, sources=context.sources, last_ndays=context.last_ndays, start=0, limit=config.filters.page.max_tags), 
            on_selection_changed=lambda selected_tags: apply_filter(filter_tags=selected_tags)
        ).classes("w-full")
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