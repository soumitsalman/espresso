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

async def render_home_page(context: Context):
    context.last_ndays = MIN_WINDOW

    await load_and_render_frame(context)
    render_banner("Briefings") 
    await _render_generated_beans_panel(context)

    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.get_beans_for_home(context.kind, context.tags, None, context.last_ndays, context.sort_by, start, limit)
    
    get_filter_tags = lambda: beanops.get_filter_tags_for_custom_page(tags=None, sources=None, last_ndays=context.last_ndays, start=0, limit=config.filters.page.max_tags)

    def apply_filter(context: Context, filter_item: str|list[str] = MAINTAIN_VALUE):
        if filter_item is not MAINTAIN_VALUE: context.tags = filter_item
        return context
    
    render_banner("News, Blogs & Articles").classes("text-h6")
    await _render_filterable_beans_panel(context, retrieve_beans, get_filter_tags, apply_filter)
    render_thick_separator()
    await load_and_render_similar_pages(context)

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
    context.last_ndays = config.filters.page.default_window

    await load_and_render_frame(context)
    render_page_banner(context)
    await _render_generated_beans_panel(context)
    
    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.get_beans_for_stored_page(context.page, context.kind, context.tags, context.last_ndays, context.sort_by, start, limit)
        
    get_filter_tags = lambda: beanops.get_filter_tags_for_stored_page(context.page, context.last_ndays, 0, config.filters.page.max_tags)

    def apply_filter(context: Context, filter_item: str|list[str] = MAINTAIN_VALUE):
        if filter_item is not MAINTAIN_VALUE: context.tags = filter_item
        return context            
    
    await _render_filterable_beans_panel(context, retrieve_beans, get_filter_tags, apply_filter)
    render_thick_separator()
    await load_and_render_similar_pages(context)    

async def render_custom_page(context: Context): 
    initial_tags = context.tags
    context.last_ndays = config.filters.page.default_window

    await load_and_render_frame(context)
    render_page_banner(context)
    if context.tags or (context.sources and 'cafecito' in context.sources): await _render_generated_beans_panel(context)
    # no point is looking for feeds
    if (context.sources and "cafecito" in context.sources): return

    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.get_beans_for_custom_page(context.kind, tags=context.tags, sources=context.sources, last_ndays=context.last_ndays, sort_by=context.sort_by, start=start, limit=limit)
        
    get_filter_tags = lambda: beanops.get_filter_tags_for_custom_page(context.tags, context.sources, context.last_ndays, 0, config.filters.page.max_tags)

    def apply_filter(context: Context, filter_item: str|list[str] = MAINTAIN_VALUE):
        if filter_item is not MAINTAIN_VALUE:
            context.tags = [initial_tags, filter_item] if (initial_tags and filter_item) else (initial_tags or filter_item)
        return context
    
    await _render_filterable_beans_panel(context, retrieve_beans, get_filter_tags, apply_filter)
    render_thick_separator()
    await load_and_render_similar_pages(context) 

async def render_bean_page(context: Context):
    context.last_ndays = config.filters.page.default_window

    await load_and_render_frame(context)
    _, bean = await load_and_render_whole_bean(context, context.page.url)
    render_thick_separator()
    await _render_related_beans_panel(context, bean)
    await load_and_render_similar_pages(context) 

async def _render_generated_beans_panel(context: Context):
    page = context.page if context.is_stored_page else None

    has_generated = await run.io_bound(beanops.count_generated_beans, page, tags=context.tags, last_ndays=context.last_ndays, limit=MIN_LIMIT)
    if not has_generated: return            

    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.get_generated_beans(page, tags=context.tags, last_ndays=context.last_ndays, start=start, limit=limit)
    
    panel = await load_and_render_beans_as_extendable_list(context, retrieve_beans)
    panel.classes("w-full")
    render_thick_separator()
    
async def _render_related_beans_panel(context: Context, bean: Bean):
    has_related = await run.io_bound(beanops.count_similar_beans, bean, kind=None, tags=context.tags, sources=context.sources, last_ndays=context.last_ndays, limit=1)
    if not has_related: return

    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.get_similar_beans(bean, context.kind, tags=context.tags, sources=context.sources, last_ndays=context.last_ndays, sort_by=context.sort_by, start=start, limit=limit)

    get_filters_items = lambda: random.sample(bean.entities, min(len(bean.entities), config.filters.page.max_tags)) if bean.entities else None

    def apply_filter(context: Context, filter_item: str|list[str] = MAINTAIN_VALUE):
        if filter_item is not MAINTAIN_VALUE: context.tags = filter_item
        return context
    
    render_banner("🗞️ Related News & Blogs").classes("text-h6")
    await _render_filterable_beans_panel(context, retrieve_beans, get_filters_items, apply_filter)
    render_thick_separator()

async def _render_filterable_beans_panel(
    context: Context, 
    retrieve_beans_func: Callable, 
    get_filter_tags: Callable = None,
    apply_filter_func: Callable = None
):
    context.kind, context.sort_by = config.filters.page.default_kind, SORT_BY_OPTIONS[config.filters.page.default_sort_by] # starting default values

    @ui.refreshable
    async def render_beans_panel(ctx: Context):   
        panel = await load_and_render_beans_as_extendable_list(ctx, retrieve_beans_func)  
        return panel.classes("w-full")
    
    def apply_filter(filter_kind: str = MAINTAIN_VALUE, filter_sort_by: str = MAINTAIN_VALUE, **kwargs):
        nonlocal context
        if filter_kind is not MAINTAIN_VALUE: context.kind = filter_kind
        if filter_sort_by is not MAINTAIN_VALUE: context.sort_by = filter_sort_by
        if kwargs and apply_filter_func: context = apply_filter_func(context, **kwargs)
        render_beans_panel.refresh(context)

    if not retrieve_beans_func: return 
    with ui.row(wrap=True, align_items="stretch").classes("w-full justify-between sm:justify-start") as filter_panel:
        render_kind_filters(context, lambda kind: apply_filter(filter_kind=kind))
        render_sort_by_filters(context, lambda sort_by: apply_filter(filter_sort_by=sort_by))
        
    await render_beans_panel(context)

    if not get_filter_tags: return
    with filter_panel:
        tags_panel = await load_and_render_filter_tags(
            context, 
            get_filter_tags, 
            on_selection_changed=lambda selected_item: apply_filter(filter_item=selected_item)
        )
        if tags_panel: tags_panel.classes("w-full lg:w-auto")

async def render_search(context: Context): 
    initial_tags, context.kind = context.tags, config.filters.page.default_kind

    await load_and_render_frame(context)
    render_search_controls(context).classes("w-full")

    def retrieve_beans(start, limit):
        context.log("retrieve", start=start, limit=limit)
        return beanops.search_beans(context.query, context.accuracy, context.kind, context.tags, context.sources, context.last_ndays, start, limit)
    
    @ui.refreshable
    async def render_search_result():
        panel = await load_and_render_beans_as_paginated_list(
            context, 
            retrieve_beans, 
            lambda: beanops.count_search_beans(context.query, context.accuracy, context.kind, context.tags, context.sources, context.last_ndays, beanops.MAX_LIMIT)
        )
        return panel.classes("w-full")               

    def apply_filter(
        filter_kind: str = MAINTAIN_VALUE, 
        filter_tags: str|list[str] = MAINTAIN_VALUE
    ):
        if filter_kind is not MAINTAIN_VALUE:    
            context.kind = filter_kind
        if filter_tags is not MAINTAIN_VALUE:
            context.tags = [initial_tags, filter_tags] if (initial_tags and filter_tags) else (initial_tags or filter_tags)
        return render_search_result.refresh()
        
    if not context.query: return
    with ui.row(wrap=True, align_items="stretch").classes("w-full") as filter_panel:
        render_kind_filters(context, lambda kind: apply_filter(filter_kind=kind))
        
    await render_search_result()
    with filter_panel:
        tags_panel = await load_and_render_filter_tags(
            context, 
            lambda: beanops.search_filter_tags(query=context.query, accuracy=context.accuracy, tags=context.tags, sources=context.sources, last_ndays=context.last_ndays, start=0, limit=config.filters.page.max_tags),
            lambda selected_item: apply_filter(filter_tags=selected_item)
        )
        if tags_panel: tags_panel.classes("w-full lg:w-auto")

async def render_registration(context: Context):
    userinfo = context.user

    async def success():
        beanops.db.create_user(userinfo, config.filters.page.default_channels)
        context.log("registered")
        internal_nav()

    async def cancel():
        context.log("cancelled")
        internal_nav()
        
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