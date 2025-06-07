from contextlib import contextmanager
import random
import threading
from typing import Callable
from urllib.parse import urlencode
from nicegui import ui, background_tasks, run
from app.pybeansack.models import *
from app.shared.utils import *
from app.shared.consts import *
from app.shared.env import *
from app.web.context import *
from app.web import beanops
from app.web.custom_ui import SwitchButton
from icecream import ic

CSS_FILE = "./app/web/styles.css"

MATERIAL_ICONS = """<link href="https://fonts.googleapis.com/icon?family=Material+Icons" rel="stylesheet">"""
GOOGLE_ANALYTICS_SCRIPT = """
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id={id}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{id}');
</script>
"""

PRIMARY_COLOR = "#4e392a"
SECONDARY_COLOR = "#b79579"
IMAGE_DIMENSIONS = "w-32"
STRETCH_FIT = "w-full h-full m-0 p-0"
ACTION_BUTTON_PROPS = "flat size=sm"
TOGGLE_OPTIONS_PROPS = "unelevated rounded no-caps color=dark toggle-color=primary"
SEARCH_BAR_PROPS = "item-aligned standout clearable clear-icon=close maxlength=1000 rounded"
BEANS_GRID_CLASSES = "w-full m-0 p-0 grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 bg-transparent"

GOOGLE_ICON = "img:https://www.google.com/favicon.ico"
REDDIT_ICON = "img:https://www.reddit.com/favicon.ico"
LINKEDIN_ICON = "img:https://www.linkedin.com/favicon.ico"
SLACK_ICON = "img:https://slack.com/favicon.ico"
TWITTER_ICON = "img:https://www.x.com/favicon.ico"
WHATSAPP_ICON = "img:/images/whatsapp.png"
ESPRESSO_ICON = "img:/images/favicon.ico"

MAX_WORD_LENGTH = 30
MAX_SUMMARY_LENGTH = 120

LOGIN_OPTIONS = [
    {
        "title": "Continue with Google",
        "icon": GOOGLE_ICON,
        "url": "/oauth/google/login"        
    },
    {
        "title": "Continue with Slack",
        "icon": SLACK_ICON,
        "url": "/oauth/slack/login"
    },
    # {
    #     "title": "Continue with LinkedIn",
    #     "icon": LINKEDIN_ICON,
    #     "url": "/oauth/linkedin/login"
    # }
]

ellipsis_word = lambda text: text[:MAX_WORD_LENGTH]+'...' if len(text) > MAX_WORD_LENGTH else text
rounded_number = lambda counter: str(counter) if counter < beanops.MAX_LIMIT else str(beanops.MAX_LIMIT-1)+'+'
rounded_number_with_max = lambda counter, top: str(counter) if counter <= top else str(top)+'+'

now = datetime.now
nav = ui.navigate.to

create_external_target = lambda base_url, **kwargs: base_url+"?"+urlencode({key: value for key, value in kwargs.items() if value})

def create_target(*args, **kwargs) -> str:
    path = "/"
    if args: path += ("/".join(x.replace('/', '%2F') for x in args))
    if kwargs:
        params = []
        kwargs = {key: value for key, value in kwargs.items() if value}
        for key, value in kwargs.items():
            if isinstance(value, list): params.extend([(key, v) for v in value if v])
            else: params.append((key, value))
        path += "?"+urlencode(params, doseq=True)
    return path

internal_nav = lambda *args, **kwargs: nav(create_target(*args, **kwargs))

def create_share_func(context: Context, bean: Bean, base_url: str):
    return lambda: [
        context.log("shared", url=bean.url, target=base_url),
        nav(create_external_target(base_url, url=bean.url, text=f"# {bean.title}\n{bean.summary}\n\n{bean.url}"), new_tab=True)
    ]

render_banner = lambda text: ui.label(text).classes("text-h5")
render_thick_separator = lambda: ui.separator().props("spaced=false").style("height: 5px;").classes("w-full")
render_share_button = lambda context, bean, base_url, icon: ui.button(on_click=create_share_func(context, bean, base_url), icon=icon, color="transparent").props("flat")

tooltip_msg = lambda ctx, msg: msg if ctx.is_registered else f"Login to {msg}"

def render_header(context: Context):
    ui.add_css(CSS_FILE, shared=True)
    ui.add_head_html(MATERIAL_ICONS, shared=True)
    ui.add_head_html(GOOGLE_ANALYTICS_SCRIPT.format(id=config.app.google_analytics_id), shared=True)
    ui.colors(primary=PRIMARY_COLOR, secondary=SECONDARY_COLOR)    

    barista_panel = render_navigation_panel(context)

    with ui.dialog() as search_dialog, ui.card(align_items="stretch").classes("w-full"):
        render_search_bar(context).classes("fit")      
        
    with ui.header(wrap=False).props("reveal").classes("justify-between items-stretch rounded-borders p-1 q-ma-xs") as header:     
        with ui.button(on_click=lambda: internal_nav()).props("unelevated").classes("q-px-xs"):
            with ui.avatar(square=True, size="md").classes("rounded-borders"):
                ui.image("images/espresso.png")
            ui.label("Espresso").classes("q-ml-sm")
            
        ui.button(icon="local_cafe_outlined", on_click=barista_panel.toggle).props("unelevated").classes("lt-sm")
        # ui.button(icon="rss_feed_outlined", on_click=barista_panel.toggle).props("unelevated").classes("lt-sm")
        ui.button(icon="search_outlined", on_click=search_dialog.open).props("unelevated").classes("lt-sm")
        render_search_bar(context).props("dense").classes("w-1/2 p-0 gt-xs")

        if context.is_registered: render_user(context.user)
        else: render_login()
    return header

def render_footer(context: Context):
    with ui.footer(fixed=False).classes("text-caption justify-center bg-transparent p-1 q-mx-xl") as footer:
        with ui.element():
            with ui.row(align_items="center").classes("gap-2 justify-between self-center text-center"):
                ui.link("Terms of Use", "https://github.com/soumitsalman/espresso/blob/main/docs/terms-of-use.md")
                ui.link("Privacy Policy", "https://github.com/soumitsalman/espresso/blob/main/docs/privacy-policy.md")
                ui.link("About", "https://github.com/soumitsalman/espresso/blob/main/README.md")
                ui.link("Project Cafecito", "https://cafecito.tech")
            ui.label("Copyright © 2024 Project Cafecito. All rights reserved.")
    return footer

def render_login():
    with ui.button(icon="login").props("unelevated") as view:
        with ui.menu().props("transition-show=jump-down transition-hide=jump-up").classes("max-w-full"):           
            for option in LOGIN_OPTIONS:
                with ui.menu_item(option["title"], on_click=lambda url=option['url']: ui.navigate.to(url)):
                    ui.avatar(option["icon"], color="transparent", square=True)
    return view

def render_user(user: User):
    with ui.button(icon="perm_identity").props("unelevated") as view:
        # with ui.avatar(color="transparent", rounded=True, size="md") as view:
        #     ui.image(user.image_url) if user.image_url else ui.icon("person")
        with ui.menu():
            with ui.item():
                ui.icon("img:"+user.image_url if user.image_url else "person", size="md").classes("q-mr-md").props("avatar")
                ui.label(user.name)
            ui.separator()
                        
            if beanops.db.get_barista(user.email):
                with ui.menu_item(on_click=lambda: internal_nav(user.email)):
                    ui.icon("bookmarks", size="md").classes("q-mr-md")
                    with ui.label("Bookmarks"):
                        ui.label("/baristas/"+user.email).classes("text-caption")
                                    
            with ui.menu_item(on_click=lambda: ui.notify("Coming soon")):
                ui.icon("settings", size="md").classes("q-mr-md")
                ui.label("Settings")

            ui.separator()
            with ui.menu_item(on_click=lambda: internal_nav("/user/me/logout")).classes("text-negative"):
                ui.icon("logout", size="md").classes("q-mr-md")
                ui.label("Log Out")
    return view

# render baristas for navigation
def render_navigation_panel(context: Context):    
    navigation_items = _create_navigation_baristas(context)

    def search_and_render_barista(text: str):
        search_results_panel.clear()
        if not text: return 
        context.log("search_barista", query=text)
        baristas = beanops.search_pages(text)
        with search_results_panel:
            if baristas: render_page_names(baristas)
            else: ui.label(NOTHING_FOUND)

    with ui.left_drawer(bordered=False).props("breakpoint=600 show-if-above").classes("q-pt-xs q-px-sm") as navigation_panel: 
        with ui.row(wrap=False, align_items="start").classes("gap-0 "+ STRETCH_FIT):

            with ui.tabs().props("vertical outside-arrows mobile-arrows shrink active-bg-color=primary indicator-color=transparent").classes("q-mt-md") as tabs:
                ui.tab("search", label="", icon="search")
                [ui.tab(item['label'], label="", icon=item['icon']).tooltip(item['label']) for item in navigation_items]
                ui.element("q-route-tab").props("href=/ icon=home_outlined")
            
            with ui.scroll_area().classes(STRETCH_FIT):
                with ui.tab_panels(tabs).props("vertical"):
                    with ui.tab_panel("search").classes(STRETCH_FIT):
                        render_navigation_search_bar(search_and_render_barista)
                        search_results_panel = render_page_names_as_list(context, None)

                    for item in navigation_items:
                        with ui.tab_panel(item['label']).classes(STRETCH_FIT):
                            render_page_names_as_list(context, item['items']).classes(STRETCH_FIT)

    if navigation_items: tabs.set_value(navigation_items[0]['label'])
        
    return navigation_panel  

def render_search_controls(context: Context):
    search_func = lambda: internal_nav("search", q=query.value, acc=accuracy.value, ndays=last_ndays.value, source=sources.value)
   
    with ui.expansion(value=False).props("dense expand-icon=tune expand-icon-toggle expand-separator") as panel:
        header = panel.add_slot("header")
        with header:
            query = render_search_input(context, search_func).classes("w-full")

        with ui.grid(columns=2).classes("w-full"):  
            with ui.list():
                with ui.item():
                    with ui.item_section().props("avatar"):
                        ui.icon("explore", color="secondary")
                    with ui.item_section() as accuracy_container:
                        accuracy = ui.slider(min=0.1, max=1.0, step=0.05, value=context.accuracy or config.filters.bean.default_accuracy)
                        accuracy_container.bind_text_from(accuracy, "value", lambda v: f"Accuracy: {v}")
                with ui.item():
                    with ui.item_section().props("avatar"):
                        ui.icon("date_range", color="secondary")
                    with ui.item_section() as last_ndays_container:
                        last_ndays = ui.slider(min=MIN_WINDOW, max=MAX_WINDOW, step=1, value=context.last_ndays or config.filters.bean.default_window).props("reverse")
                        last_ndays_container.bind_text_from(last_ndays, "value", 
                            lambda v: f"Since {(datetime.now() - timedelta(days=v)).strftime('%b %d')}")
            sources = ui.select(options=beanops.get_all_sources(), value=context.sources, label="Feeds", with_input=True, multiple=True, clearable=True) \
                .props("standout max-values=20 dropdown-icon=rss_feed dense clear-icon=close").classes("text-caption")
    return panel

def render_search_bar(context: Context):
    search_func = lambda: internal_nav("search", q=search_input.value)
    search_input = render_search_input(context, search_func)
    return search_input

def render_search_input(context: Context, trigger_search: Callable):
    with ui.input(placeholder=SEARCH_BEANS_PLACEHOLDER, value=context.query) \
        .on("keydown.enter", trigger_search) \
        .props(SEARCH_BAR_PROPS) \
        as search_input:    
        prepend = search_input.add_slot("prepend")   
        with prepend:
            ui.button(icon="search", color="secondary", on_click=trigger_search).bind_visibility_from(search_input, "value").props("round flat dense").classes("m-0")
    return search_input

def render_navigation_search_bar(search_func: Callable):
    trigger_search = lambda: search_func(search_input.value)
    search_input = ui.input(placeholder=SEARCH_BARISTA_PLACEHOLDER) \
        .on("keydown.enter", trigger_search) \
        .on("clear", trigger_search) \
        .props("dense standout clearable clear-icon=close")
    return search_input

render_page_names = lambda pages: [ui.item(item.title).props(f"clickable standout href='/pages/{item.id}'").classes("bg-dark rounded-borders") for item in pages]

def render_page_names_as_list(context: Context, baristas: list[Page]):
    with ui.list() as holder:
        if baristas: render_page_names(baristas)
    return holder 

def render_page_banner(context: Context):
    if context.page_type == "stored_page": banner_text = f"☕ {context.page.title}"
    elif context.page_type == K_CATEGORIES: banner_text = f"🏷️ {context.page}"
    elif context.page_type == K_REGIONS: banner_text = f"📍 {context.page}"
    elif context.page_type == K_RELATED: banner_text = f"🗞️ {context.page.title}"
    elif context.page_type == GENERATED: banner_text = context.page.title
    else: banner_text = context.page

    with render_banner(banner_text) as view:
        if context.is_stored_page:
            with ui.button(icon="more_vert").props("flat").classes("q-ml-md"):
                with ui.menu():  
                    # with ui.item("Public"):
                    #     ui.switch(value=barista.public, on_change=lambda: toggle_publish(context)).props("flat checked-icon=public unchecked-icon=public_off")
                    with ui.item("Follow"):
                        ui.switch(value=context.is_following, on_change=lambda: toggle_follow(context)).props("flat checked-icon=playlist_add_check").tooltip(tooltip_msg(context, "Follow")).set_enabled(context.has_follow_permission)
                    with ui.menu_item("Pour a Filtered Cup", on_click=lambda: ui.notify("Coming soon")):
                        ui.avatar(icon="filter_list", color="transparent") 
    return view

def render_filter_tags(context: Context, load_items: Callable, on_selection_changed: Callable):
    async def render():
        items = await run.io_bound(load_items)
        if not items: return
        with holder:
            with ui.tabs(on_change=lambda e: on_selection_changed([e.sender.value])) \
                .props("dense shrink no-caps mobile-arrows active-bg-color=primary indicator-color=transparent") as filter_panel:                
                if isinstance(items, list): [ui.tab(item).classes("rounded-full bg-dark q-mr-sm") for item in items]
                elif isinstance(items, dict): [ui.tab(k, label=v).classes("rounded-full bg-dark q-mr-sm") for k, v in items.items()]
                ui.button(icon="close", color="grey-4", on_click=lambda: filter_panel.set_value(None)).props("flat dense round")

    holder = ui.row(align_items="stretch", wrap=False)
    background_tasks.create_lazy(render(), name=f"filter-items-{now()}")
    return holder

def render_similar_pages(context: Context):
    related_baristas = beanops.get_pages(context.page.related) \
        if (context.is_stored_page and context.page.related) \
            else beanops.get_page_suggestions(context)
    
    with ui.row().classes("w-full gap-1"):
        render_page_names(related_baristas)

render_grid = lambda: ui.grid().classes(BEANS_GRID_CLASSES)

def render_beans(context: Context, load_beans: Callable, container: ui.element = None, item_classes: str = STRETCH_FIT):
    async def render():
        beans = await run.io_bound(load_beans)
        container.clear()
        with container:
            if beans: [render_bean_with_related(context, bean).classes(item_classes) for bean in beans] 
            else: ui.label(NOTHING_FOUND).classes("w-full text-center") 

    container = container or render_grid()
    with container:
        render_skeleton_beans(3)
    background_tasks.create_lazy(render(), name=f"beans-{now()}")
    return container

def render_beans_as_extendable_list(context: Context, load_beans: Callable):
    current_start = 0   
    
    def current_page():
        nonlocal current_start
        beans = load_beans(current_start, config.filters.page.max_beans+1) 
        if not beans: return
        current_start += config.filters.page.max_beans # moving the cursor
        if len(beans) <= config.filters.page.max_beans:
            more_btn.delete()
        return beans[:config.filters.page.max_beans]

    async def next_page():
        with disable_button(more_btn):
            beans = await run.io_bound(current_page)   
            with beans_panel:
                [render_bean_with_related(context, bean).classes(STRETCH_FIT) for bean in beans[:config.filters.page.max_beans]]

    with ui.column() as view:
        with render_grid() as beans_panel:
            render_beans(context, current_page, beans_panel, STRETCH_FIT)
        more_btn = ui.button("More Stories", on_click=next_page).props("rounded no-caps icon-right=chevron_right")
    return view

def render_beans_as_paginated_list(context: Context, load_beans: Callable, count_items: Callable):    
    @ui.refreshable
    def render(page):
        return render_beans(context, lambda: load_beans((page-1)*config.filters.page.max_beans, config.filters.page.max_beans)).classes("w-full")     

    with ui.column(align_items="stretch") as panel:
        render(1)
        render_pagination(count_items, lambda page: render.refresh(page))
    return panel

def render_bean_with_related(context: Context, bean: Bean):
    related_beans: list[Bean] = None

    def render_bean_as_slide(item: Bean, expanded: bool, on_read: Callable):
        with ui.carousel_slide(item.url).classes("w-full m-0 p-0 no-wrap"):
            render_bean(context, item, expanded, on_read)

    async def on_read():
        nonlocal related_beans
        if related_beans: return
        related_beans = await run.io_bound(beanops.get_related_beans, url=bean.url, kind=None, tags=None, sources=None, last_ndays=None, sort_by=None, start=0, limit=config.filters.bean.max_related)
        if not related_beans: return
        with carousel:
            for item in related_beans:
                render_bean_as_slide(item, True, None) # NOTE: keep them expanded by default and no need for callback

    with ui.item() as view:  # Added rounded-borders class here
        with ui.carousel(
            animated=True, 
            arrows=True, 
            value=bean.url,
            on_value_change=lambda e: context.log("read", url=e.sender.value)
        ).props("swipeable control-color=secondary").classes("rounded-borders w-full h-full") as carousel:
            render_bean_as_slide(bean, False, on_read) # NOTE: closed by default and make a callback to load related beans
            
    return view

# render_bean = lambda user, bean, expandable: render_expandable_bean(user, bean) if expandable else render_whole_bean(user, bean)
def render_expandable_bean(context: Context, bean: Bean, expanded: bool = False, on_expanded = None):
    body_loaded = expanded
    async def load_body():
        nonlocal body_loaded
        if not expansion.value: return
        context.log("read", url=bean.url)

        if body_loaded: return
        with expansion: 
            render_bean_body(context, beanops.load_bean_body(bean))
            body_loaded = True

    with ui.expansion(value=expanded, on_value_change=load_body) \
        .on_value_change(load_body) \
        .on_value_change(on_expanded) \
        .props("dense hide-expand-icon") \
        .classes("bg-dark rounded-borders " + STRETCH_FIT) as expansion:
        header = expansion.add_slot("header")
        with header:    
            render_bean_header(context, bean).classes(add="p-0")
        if expanded:
            render_bean_body(context, bean)
    return expansion

def render_whole_bean(context: Context, bean: Bean):
    with ui.column(align_items="stretch") as view:
        render_bean_header(context, bean).classes(add="q-mb-sm")
        render_bean_body(context, bean)
    return view 

def render_bean(context, bean, expanded: bool = False, on_expanded = None):
    if config.rendering.bean.body == "whole": return render_whole_bean(context, bean)
    return render_expandable_bean(context, bean, expanded, on_expanded)

def render_bean_header(context: Context, bean: Bean):
    with ui.row(wrap=False, align_items="stretch").classes("w-full bean-header") as view:            
        if bean.image_url: ui.image(bean.image_url).classes(IMAGE_DIMENSIONS)
        with ui.element().classes("w-full"):
            ui.label(bean.title).classes("bean-title")  
            render_all_bean_attributes(context, bean).classes("m-0")
            # render_bean_source_attributes(context, bean).classes("my-1")
            # render_bean_stats_and_classification(context, bean)
    return view

render_attribute_as_link = lambda prefix, title, target: ui.markdown((f"{prefix} " if prefix else "")+f"[{title}]({target})").classes("max-w-[25ch] ellipsis")

def render_attribute_as_chip(title, target=None): 
    with ui.chip(
        color="transparent", 
        on_click=(lambda: nav(target)) if target else None
    ).props("dense flat").classes("m-0 text-caption max-w-[25ch]").tooltip(title) as view:
        ui.label(title).classes("ellipsis")
    return view

def render_bean_source_attributes(context: Context, bean: Bean):
    with ui.row(align_items="center", wrap=False).classes("gap-2") as view:
        render_attribute_as_chip(naturalday(bean.created))
        render_attribute_as_chip(bean.site_name or bean.source, create_target("sources", bean.source)).props("icon=img:"+favicon(bean))
        if bean.author: render_attribute_as_chip(f"✍️ {bean.author}").classes(remove="max-w-[25ch]", add="max-w-[12ch]")
    return view

# def render_bean_source(context: Context, bean: Bean):
#     with render_bean_attribute('', create_page_target("/sources", bean.source)) as view:        
#         ui.icon("img:"+ favicon(bean)).classes("mr-1")
#         ui.label(bean.site_name or bean.source)
#     return view
    # with ui.row(wrap=False, align_items="center").classes("gap-1") as view:        
    #     ui.icon("img:"+ favicon(bean), size="xs")
    #     render_bean_attribute(bean.site_name or bean.source, create_page_target("/sources", bean.source))
    # return view

def render_bean_stats_and_classification(context: Context, bean: Bean): 
    with ui.row(align_items="center").classes("gap-2") as view:    
        if bean.categories: render_attribute_as_chip(f"🏷️ {bean.categories[0]}", create_target('categories', bean.categories[0]))         
        if bean.regions: render_attribute_as_chip(f"📍 {bean.regions[0]}", create_target('regions', bean.regions[0]))
        if bean.related: render_attribute_as_chip(f"🗞️ {bean.related}", create_target('related', url=bean.url)).tooltip(f"{bean.related} related article(s)")
        if bean.comments: render_attribute_as_chip(f"💬 {naturalnum(bean.comments)}").tooltip(f"{bean.comments} comments across various social media sources")
        if bean.likes: render_attribute_as_chip(f"👍 {naturalnum(bean.likes)}").tooltip(f"{bean.likes} likes across various social media sources")
        if bean.shares: render_attribute_as_chip(f"🔗 {bean.shares}").tooltip(f"{bean.shares} shares across various social media sources") # another option 🗞️    
    return view

def render_bean_classification(context: Context, bean: Bean): 
    with ui.row(align_items="center", wrap=False).classes("gap-3") as view:    
        if bean.categories: render_attribute_as_chip(f"🏷️ {bean.categories[0]}", create_target('categories', bean.categories[0]))           
        if bean.regions: render_attribute_as_chip(f"📍 {bean.regions[0]}", create_target('regions', bean.regions[0]))
    return view

def render_bean_stats(context: Context, bean: Bean): 
    with ui.row(align_items="center", wrap=False).classes("gap-3") as view:    
        if bean.comments: render_attribute_as_chip(f"💬 {naturalnum(bean.comments)}").tooltip(f"{bean.comments} comments across various social media sources")
        if bean.likes: render_attribute_as_chip(f"👍 {naturalnum(bean.likes)}").tooltip(f"{bean.likes} likes across various social media sources")
        if bean.shares and bean.shares > 1: render_attribute_as_chip(f"🔗 {bean.shares}").tooltip(f"{bean.shares} shares across various social media sources") # another option 🗞️
        if bean.related: render_attribute_as_chip(f"🗞️ {bean.related}", create_target('related', url=bean.url)).tooltip(f"{bean.related} related article(s)")
    return view

def render_all_bean_attributes(context: Context, bean: Bean):
    with ui.row(align_items="center").classes("gap-2") as view:
        render_attribute_as_chip(naturalday(bean.created))
        render_attribute_as_chip(bean.site_name or bean.source, create_target("sources", bean.source)).props("icon=img:"+favicon(bean))
        if bean.author: render_attribute_as_chip(f"✍️ {bean.author}").classes(remove="max-w-[25ch]", add="max-w-[15ch]")    
        if bean.categories: render_attribute_as_chip(f"🏷️ {bean.categories[0]}", create_target('categories', bean.categories[0]))         
        if bean.regions: render_attribute_as_chip(f"📍 {bean.regions[0]}", create_target('regions', bean.regions[0]))
        # if bean.related: render_attribute_as_chip(f"🗞️ {bean.related}", create_target('related', url=bean.url)).tooltip(f"{bean.related} related article(s)")
        if bean.comments: render_attribute_as_chip(f"💬 {naturalnum(bean.comments)}").tooltip(f"{bean.comments} comments across various social media sources")
        if bean.likes: render_attribute_as_chip(f"👍 {naturalnum(bean.likes)}").tooltip(f"{bean.likes} likes across various social media sources")
        if bean.shares and bean.shares > 1: render_attribute_as_chip(f"🔗 {bean.shares}").tooltip(f"{bean.shares} shares across various social media sources") # another option 🗞️    
    return view

def render_bean_body(context: Context, bean: Bean):
    with ui.column(align_items="stretch").classes("w-full m-0 p-0") as view:
        if bean.entities: render_bean_entities(context, bean)
        if bean.summary: ui.markdown(bean.summary).classes("bean-body truncate-multiline")
        ui.link("Read More ...", bean.url if bean.kind != GENERATED else create_target('articles', bean.url), new_tab=True).on("click", lambda : context.log("opened", url=bean.url))
        render_bean_actions(context, bean).classes(STRETCH_FIT)
    return view

def render_entities_as_chips(context: Context, bean: Bean):
    as_chip = lambda tag: ui.chip(
        tag, 
        on_click=lambda tag=tag: internal_nav('entities', tag)
    ).props("square").classes("max-w-[30ch]")

    with ui.row(wrap=True, align_items="baseline").classes("gap-1") as view:
        list(map(
            as_chip, 
            random.sample(bean.entities, min(config.filters.page.max_tags, len(bean.entities)))
        ))
    return view

def render_bean_entities(context: Context, bean: Bean):
    as_link = lambda tag: ui.link(
        tag, 
        target=create_target('entities', tag)
    ) \
    .classes("q-mr-md max-w-[30ch] ellipsis") \
    .style("color: secondary; text-decoration: none;")
    
    with ui.row(wrap=True, align_items="baseline").classes("gap-0 m-0 p-0 text-caption") as view:
        list(map(
            as_link, 
            random.sample(bean.entities, min(config.filters.bean.max_entities, len(bean.entities)))
        ))
    return view

def render_bean_actions(context: Context, bean: Bean): 
    bug_report = render_report_a_bug()

    async def show_bug_report():
        issue = await bug_report
        if issue: context.log("reported", url=bean.url, bug=issue)

    with ui.row(wrap=False, align_items="center").classes("justify-between") as view:
        with ui.button_group().props(ACTION_BUTTON_PROPS).classes("p-0 m-0"):
            SwitchButton(
                beanops.is_bookmarked(context, bean.url), 
                unswitched_icon="bookmark_outlined", switched_icon="bookmark", 
                color="secondary",
                on_click=lambda: toggle_bookmark(context, bean)
            ) \
                .props(ACTION_BUTTON_PROPS) \
                .tooltip(tooltip_msg(context, "Bookmark")) \
                .set_enabled(context.is_registered)
            
            # ui.button(
            #     icon="bug_report", 
            #     color="secondary", 
            #     on_click=show_bug_report
            # ) \
            #     .props(ACTION_BUTTON_PROPS) \
            #     .tooltip(tooltip_msg(context, "Report Bug")) \
            #     .set_enabled(context.is_registered)

        with ui.button_group().props(ACTION_BUTTON_PROPS).classes("p-0 m-0"):
            # ui.button(icon="rss_feed", color="secondary", on_click=lambda: navigate_to_source(bean.source)).props(ACTION_BUTTON_PROPS).tooltip("More from this channel")
            ui.button(icon="search", color="secondary", on_click=lambda: internal_nav("search", q=bean.url)).props(ACTION_BUTTON_PROPS).tooltip("More like this")
            with ui.button(icon="share", color="secondary").props(ACTION_BUTTON_PROPS):
                with ui.menu().props("auto-close"):
                    with ui.row(wrap=False, align_items="stretch").classes("gap-1 m-0 p-0"):
                        render_share_button(context, bean, "https://www.reddit.com/submit", REDDIT_ICON).tooltip("Share on Reddit")
                        render_share_button(context, bean, "https://www.linkedin.com/shareArticle", LINKEDIN_ICON).tooltip("Share on LinkedIn")
                        render_share_button(context, bean, "https://x.com/intent/tweet", TWITTER_ICON).tooltip("Share on X")
                        render_share_button(context, bean, "https://wa.me/", WHATSAPP_ICON).tooltip("Share on WhatsApp")
                        # share_button("https://slack.com/share/url", SLACK_ICON).tooltip("Share on Slack") 
    return view  

def render_report_a_bug():
    with ui.dialog() as dialog, ui.card():
        with ui.row(wrap=False):
            ui.icon("bug_report")
            ui.label("Don't like it? Report it!")
        with ui.row():
            ui.button("Category/Scope WTF", on_click=lambda: dialog.submit("Category/Scope WTF"))
            ui.button("Summary/Title WTF", on_click=lambda: dialog.submit("Summary/Title WTF"))
            ui.button("Ugly AF", on_click=lambda: dialog.submit("Ugly AF"))
        other_text = ui.input(placeholder="Cry me a river").props("standout").classes("w-full")
        with ui.row(wrap=False).classes("self-end"):
            ui.button("Report", on_click=lambda: dialog.submit(other_text.value)).bind_visibility_from(other_text, "value", lambda v: v and len(v.split()) >=3)
            ui.button("Cancel", color="negative", on_click=lambda: dialog.submit(False))
    return dialog

def render_pagination(count_items: Callable, on_change: Callable):
    async def render():
        items_count = await run.io_bound(count_items)
        page_count = -(-items_count//config.filters.page.max_beans)
        view.clear()
        if items_count > config.filters.page.max_beans:
            with view:
                ui.pagination(min=1, max=page_count, direction_links=True, on_change=lambda e: on_change(e.sender.value)).props("max-pages=10 ellipses")            

    with ui.element() as view:
        ui.skeleton("rect", width="100%").classes("w-full")
    background_tasks.create_lazy(render(), name=f"pagination-{now()}")
    return view

def render_skeleton_beans(count = 3):
    skeletons = []
    for _ in range(count):
        with ui.item().classes("w-full") as item:
            with ui.item_section().props("side"):
                ui.skeleton("rect", size="8em")
            with ui.item_section().props("top"):
                ui.skeleton("text", width="100%")
                ui.skeleton("text", width="100%")
                ui.skeleton("text", width="40%")
        skeletons.append(item)
    return skeletons

def render_skeleton_baristas(count = 3):
    skeletons = []
    for _ in range(count):
        with ui.item().classes("w-full") as item:
            with ui.item_section().props("side"):
                ui.skeleton("rect", size="8em")
            with ui.item_section().props("top"):
                ui.skeleton("text", width="40%")
                ui.skeleton("text", width="100%")    
        skeletons.append(item)
    return skeletons

def render_error_text(msg: str):
    return ui.label(msg).classes("self-center text-center")

def render_card_container(label: str, on_click: Callable = None, header_classes: str = "text-h6"):
    with ui.card(align_items="stretch").tight().props("flat") as panel:        
        holder = ui.item(label, on_click=on_click).classes(header_classes)
        if on_click:
            holder.props("clickable").tooltip("Click for more")
        ui.separator().classes("q-mb-xs") 
    return panel

def toggle_bookmark(context: Context, bean: Bean):
    if not context.is_registered: return False

    if beanops.db.is_bookmarked(context.user, bean.url):
        beanops.db.unbookmark(context.user, bean.url)   
        context.log("unbookmarked", url=bean.url)         
    else:
        beanops.db.bookmark(context.user, bean.url)
        context.log("bookmarked", url=bean.url)

    return True

def toggle_publish(context: Context):
    if not context.has_publish_permission: return False

    barista = context.page
    if beanops.db.is_published(barista.id):
        beanops.db.unpublish(barista.id)
        context.log("unpublished", page_id=barista.id)  
    else:
        beanops.db.publish(barista.id)
        context.log("published", page_id=barista.id)

    return True

def toggle_follow(context: Context):
    if not context.has_follow_permission: return False

    barista = context.page
    if barista.id not in context.user.following:
        beanops.db.follow_barista(context.user.email, barista.id)
        context.log("followed", page_id=barista.id)
    else:
        beanops.db.unfollow_barista(context.user.email, barista.id)
        context.log("unfollowed", page_id=barista.id)

    return True

@contextmanager
def disable_button(button: ui.button):
    button.disable()
    button.props(add="loading")
    try:
        yield
    finally:
        button.props(remove="loading")
        button.enable()

def create_debounce(func, wait):
    last_call = None
    def debounced(*args, **kwargs):
        nonlocal last_call
        if last_call:
            last_call.cancel()
        last_call = threading.Timer(wait, func, args, kwargs)
        last_call.start()
    return debounced

def _create_navigation_baristas(context: Context):
    items = [
        {
            "icon": "web_stories", # local_cafe_outlined # newsstand # web_stories # bookmarks # browse
            "label": "Following",
            "items": beanops.get_following_pages(context.user) if context.is_registered else None
        },
        {
            "icon": "label_outlined",
            "label": "Channels",
            "items": beanops.get_pages(config.navigation.default_pages)
        },
        # {
        #     "icon": "rss_feed",
        #     "label": "Outlets",
        #     "items": beanops.get_baristas(DEFAULT_OUTLET_BARISTAS)
        # },
        # {
        #     "icon": "tag",
        #     "label": "Tags",
        #     "items": beanops.get_baristas(DEFAULT_TAG_BARISTAS)
        # },
        # {
        #     "icon": "scatter_plot",
        #     "label": "Explore",
        #     "items": beanops.get_barista_recommendations(context)
        # }
        
    ]
    return [item for item in items if item["items"]]