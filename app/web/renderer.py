from contextlib import contextmanager
import random
import threading
from typing import Callable
import inflect
from urllib.parse import urlencode
from nicegui import ui, background_tasks, run
from app.pybeansack.models import *
from app.shared.utils import *
from app.shared.messages import *
from app.shared.env import *
from app.shared import beanops
from app.web.custom_ui import SwitchButton
from icecream import ic

PRIMARY_COLOR = "#4e392a"
SECONDARY_COLOR = "#b79579"
IMAGE_DIMENSIONS = "w-32"
STRETCH_FIT = "w-full h-full m-0 p-0"
ELLISPSIS_LENGTH = 30
CSS_FILE = "./app/web/styles.css"

GOOGLE_ICON = "img:https://www.google.com/favicon.ico"
REDDIT_ICON = "img:https://www.reddit.com/favicon.ico"
LINKEDIN_ICON = "img:https://www.linkedin.com/favicon.ico"
SLACK_ICON = "img:https://slack.com/favicon.ico"
TWITTER_ICON = "img:https://www.x.com/favicon.ico"
WHATSAPP_ICON = "img:/images/whatsapp.png"
ESPRESSO_ICON = "img:/images/favicon.ico"

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

inflect_engine = inflect.engine()

ellipsis_text = lambda text: text[:ELLISPSIS_LENGTH]+'...' if len(text) > ELLISPSIS_LENGTH else text
rounded_number = lambda counter: str(counter) if counter < beanops.MAX_LIMIT else str(beanops.MAX_LIMIT-1)+'+'
rounded_number_with_max = lambda counter, top: str(counter) if counter <= top else str(top)+'+'

def create_navigation_target(base_url: str, **kwargs) -> str:
    if kwargs:
        return base_url+"?"+urlencode(query={key:value for key, value in kwargs.items() if value})
    return base_url

def create_search_target(query = None, tag = None):
    if query: return create_navigation_target("/search", query=query)
    if tag: return create_navigation_target("/search", tag=tag)
    return create_navigation_target("/search")

def create_barista_target(barista_id = None, source = None, tag = None):
    if barista_id: return f"/baristas/{barista_id}"
    if source: return create_navigation_target("/baristas", source=source)
    if tag: return create_navigation_target("/baristas", tag=tag)

navigate_to = lambda base_url, **kwargs: ui.navigate.to(create_navigation_target(base_url, **kwargs))
navigate_to_barista = lambda barista_id = None, source = None, tag = None: ui.navigate.to(create_barista_target(barista_id, source, tag))
navigate_to_search = lambda query = None, tags = None: ui.navigate.to(create_search_target(query, tags))

def render_banner(text: str|list[str]):
    banner_text = inflect_engine.join(text) if isinstance(text, list) else text
    return ui.label(banner_text).classes("text-h6")

def render_header(user: User):
    ui.add_css(CSS_FILE)
    ui.colors(primary=PRIMARY_COLOR, secondary=SECONDARY_COLOR)    

    barista_panel = render_navigation_panel(user)
        
    with ui.header(wrap=False).props("reveal").classes("justify-between items-stretch rounded-borders p-1 q-ma-xs") as header:     
        with ui.button(on_click=barista_panel.toggle).props("unelevated").classes("q-px-xs"):
            with ui.avatar(square=True, size="md").classes("rounded-borders"):
                ui.image("images/cafecito.png")
            ui.label("Espresso").classes("q-ml-sm")
            
        ui.button(icon="home_outlined", on_click=lambda: navigate_to("/")).props("unelevated").classes("lt-sm")
        ui.button(icon="search_outlined", on_click=navigate_to_search).props("unelevated").classes("lt-sm")

        trigger_search = lambda: navigate_to_search(search_input.value)
        with ui.input(placeholder=SEARCH_BEANS_PLACEHOLDER) \
            .props('item-aligned dense standout clearable clear-icon=close maxlength=1000') \
            .classes("gt-xs w-1/2 m-0 p-0") \
            .on("keydown.enter", trigger_search) as search_input:    
            prepend = search_input.add_slot("prepend")   
            with prepend:
                ui.button(icon="search", color="secondary", on_click=trigger_search).props("flat rounded").classes("m-0")
                
        (render_user(user) if isinstance(user, User) else render_login()).props("unelevated")
    return header

def render_login():
    with ui.button(icon="login") as view:
        with ui.menu().props("transition-show=jump-down transition-hide=jump-up").classes("max-w-full"):           
            for option in LOGIN_OPTIONS:
                with ui.menu_item(option["title"], on_click=lambda url=option['url']: ui.navigate.to(url)):
                    ui.avatar(option["icon"], color="transparent", square=True)
    return view

def render_user(user: User):
    with ui.button(icon="person") as view:
        # with ui.avatar(color="transparent", rounded=True, size="md") as view:
        #     ui.image(user.image_url) if user.image_url else ui.icon("person")
        with ui.menu():
            with ui.item():
                ui.icon("img:"+user.image_url if user.image_url else "person", size="md").classes("q-mr-md").props("avatar")
                ui.label(user.name)
            ui.separator()
                        
            if beanops.db.get_barista(user.email):
                with ui.menu_item(on_click=lambda: navigate_to_barista(user.email)):
                    ui.icon("bookmarks", size="md").classes("q-mr-md")
                    with ui.label("Bookmarks"):
                        ui.label("/baristas/"+user.email).classes("text-caption")
                                    
            with ui.menu_item(on_click=lambda: ui.notify("Coming soon")):
                ui.icon("settings", size="md").classes("q-mr-md")
                ui.label("Settings")

            ui.separator()
            with ui.menu_item(on_click=lambda: navigate_to("/user/me/logout")).classes("text-negative"):
                ui.icon("logout", size="md").classes("q-mr-md")
                ui.label("Log Out")
    return view

# render baristas for navigation
def render_navigation_panel(user: User|str|None):    
    navigation_items = _create_navigation_baristas(user)

    def search_barista(text: str):
        search_results_panel.clear()
        if not text: return 
        log("search_barista", user_id=user, query=text)
        baristas = beanops.search_baristas(user, text)
        with search_results_panel:
            if baristas: render_barista_items(baristas)
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
                        render_search_bar(search_barista, SEARCH_BARISTA_PLACEHOLDER)
                        search_results_panel = render_baristas(None)

                    for item in navigation_items:
                        with ui.tab_panel(item['label']).classes(STRETCH_FIT):
                            render_baristas(item['items']).classes(STRETCH_FIT)

        tabs.set_value(navigation_items[0]['label'])
        
    return navigation_panel  

def render_search_bar(search_func: Callable, search_placeholder: str = SEARCH_BEANS_PLACEHOLDER):
    trigger_search = lambda: search_func(search_input.value)
    search_input = ui.input(placeholder=search_placeholder) \
        .on("keydown.enter", trigger_search) \
        .on("clear", trigger_search) \
        .props("dense standout clearable clear-icon=close")
    return search_input

render_barista_items = lambda baristas: [ui.item(item.title, on_click=lambda item=item: navigate_to_barista(item.id)).classes("w-full") for item in baristas]

def render_baristas(baristas: list[Barista]):
    with ui.list() as holder:
        if baristas: render_barista_items(baristas)
    return holder 

def render_beans(user: User, load_beans: Callable, container: ui.element = None):
    async def render():
        beans = await run.io_bound(load_beans)
        container.clear()
        with container:
            if not beans:
                ui.label(NOTHING_FOUND).classes("w-full text-center") 
            [render_bean_with_related(user, bean).classes("w-full w-full m-0 p-0") for bean in beans] 

    container = container or ui.column(align_items="stretch")
    with container:
        render_skeleton_beans(3)
    background_tasks.create_lazy(render(), name=f"beans-{now()}")
    return container

def render_beans_as_extendable_list(user: User, load_beans: Callable, container: ui.element = None):
    current_start = 0   

    def current_page():
        nonlocal current_start
        beans = load_beans(current_start, MAX_ITEMS_PER_PAGE+1) 
        current_start += MAX_ITEMS_PER_PAGE # moving the cursor
        if len(beans) <= MAX_ITEMS_PER_PAGE:
            more_btn.delete()
        return beans[:MAX_ITEMS_PER_PAGE]

    async def next_page():
        with disable_button(more_btn):
            beans = await run.io_bound(current_page)   
            with beans_panel:
                [render_bean_with_related(user, bean).classes("w-full w-full m-0 p-0") for bean in beans[:MAX_ITEMS_PER_PAGE]]

    with ui.column() as view:
        beans_panel = render_beans(user, current_page, container).classes("w-full")
        more_btn = ui.button("More Stories", on_click=next_page).props("icon-right=chevron_right")
    return view  

def render_beans_as_paginated_list(user: User, load_beans: Callable, count_items: Callable):    
    @ui.refreshable
    def render(page):
        return render_beans(user, lambda: load_beans((page-1)*MAX_ITEMS_PER_PAGE, MAX_ITEMS_PER_PAGE)).classes("w-full")     

    with ui.column(align_items="stretch") as panel:
        render(1)
        render_pagination(count_items, lambda page: render.refresh(page))
    return panel

def render_bean_with_related(user: User, bean: Bean):
    related_beans: list[Bean] = None

    def render_bean_as_slide(item: Bean, expanded: bool, on_read: Callable):
        with ui.carousel_slide(item.url).classes("w-full m-0 p-0 no-wrap"):
            render_bean(user, item, expanded, on_read).classes("w-full m-0 p-0")

    def on_read():
        nonlocal related_beans
        if related_beans: return
        related_beans = beanops.get_related(url=bean.url, tags=None, kinds=None, sources=None, last_ndays=None, limit=MAX_RELATED_ITEMS)
        with carousel:
            for item in related_beans:
                render_bean_as_slide(item, True, None) # NOTE: keep them expanded by default and no need for callback

    with ui.item() as view:  # Added rounded-borders class here
        with ui.carousel(
            animated=True, 
            arrows=True, 
            value=bean.url,
            on_value_change=lambda e: log("read", user_id=user, url=e.sender.value)
        ).props("swipeable control-color=secondary").classes("rounded-borders w-full h-full") as carousel:
            render_bean_as_slide(bean, False, on_read) # NOTE: closed by default and make a callback to load related beans
            
    return view

# render_bean = lambda user, bean, expandable: render_expandable_bean(user, bean) if expandable else render_whole_bean(user, bean)
render_bean = lambda user, bean, expanded, on_read: render_expandable_bean(user, bean, expanded, on_read)
def render_expandable_bean(user: User, bean: Bean, expanded: bool = False, on_read: Callable = None):

    async def on_expanded():
        if not expansion.value: return
        log("read", user_id=user, url=bean.url)
        if on_read: 
            await run.io_bound(on_read)

    with ui.expansion(value=expanded, on_value_change=on_expanded).props("dense hide-expand-icon").classes("bg-dark rounded-borders") as expansion:
        header = expansion.add_slot("header")
        with header:
            render_bean_header(user, bean).classes(add="p-0")
        render_bean_body(user, bean)
    return expansion

def render_whole_bean(user: User, bean: Bean):
    with ui.element() as view:
        render_bean_header(user, bean).classes(add="q-mb-sm")
        render_bean_body(user, bean)
    return view 

def render_bean_header(user: User, bean: Bean):
    with ui.row(wrap=False, align_items="stretch").classes("w-full bean-header") as view:            
        if bean.image_url: 
            ui.image(bean.image_url).classes(IMAGE_DIMENSIONS)
        with ui.element().classes("w-full"):
            ui.label(bean.title).classes("bean-title")                
            render_bean_stats(user, bean).classes("text-caption") 
            render_bean_source(user, bean).classes("text-caption") 
    return view

def render_bean_stats(user: User, bean: Bean): 
    with ui.row(align_items="center").classes("w-full gap-3") as view:       
        ui.label(naturalday(bean.created or bean.updated))
        if bean.comments:
            ui.label(f"💬 {bean.comments}").tooltip(f"{bean.comments} comments across various social media sources")
        if bean.likes:
            ui.label(f"👍 {bean.likes}").tooltip(f"{bean.likes} likes across various social media sources")
        if bean.shares and bean.shares > 1:
            ui.label(f"🔗 {bean.shares}").tooltip(f"{bean.shares} shares across various social media sources") # another option 🗞️
    return view

def render_bean_body(user: User, bean: Bean):
    with ui.column(align_items="stretch").classes("w-full m-0 p-0") as view:
        if bean.tags:
            render_bean_tags(user, bean)
        if bean.summary:
            ui.markdown(bean.summary).classes("bean-body").tooltip("AI generated summary")
        with ui.row(wrap=False, align_items="stretch").classes("w-full p-0 m-0 justify-end"):
            # render_bean_source(user, bean).classes("text-caption bean-source")
            render_bean_actions(user, bean)
    return view

def render_bean_tags(user: User, bean: Bean):
    make_tag = lambda tag: ui.link(tag, target=create_search_target(tag=tag)).classes("tag q-mr-md").style("color: secondary; text-decoration: none;")
    with ui.row(wrap=True, align_items="baseline").classes("w-full gap-0 m-0 p-0 text-caption") as view:
        [make_tag(tag) for tag in random.sample(bean.tags, min(MAX_TAGS_PER_BEAN, len(bean.tags)))]
    return view

def render_bean_source(user: User, bean: Bean):
    with ui.row(wrap=False, align_items="center").classes("gap-2") as view:        
        ui.icon("img:"+ favicon(bean))
        ui.link(bean.source, bean.url, new_tab=True).classes("ellipsis-30").on("click", lambda : log("opened", user_id=user, url=bean.url))
    return view

def render_bean_actions(user: User, bean: Bean): 
    share_text = f"{bean.summary}\n\n{bean.url}"  
    
    def share_func(target: str):
        return lambda: [
            log("shared", user_id=user, url=bean.url, target=target),
            ui.navigate.to(create_navigation_target(target, url=bean.url, text=share_text), new_tab=True)
        ]
    share_button = lambda target, icon: ui.button(on_click=share_func(target), icon=icon, color="transparent").props("flat")
        
    with ui.button_group().props("flat size=sm").classes("p-0 m-0"):
        ui.button(icon="rss_feed", color="secondary", on_click=lambda: navigate_to_barista(source=bean.source)).props("flat size=sm").tooltip("More from this channel")
        ui.button(icon="search", color="secondary", on_click=lambda: navigate_to_search(bean.url)).props("flat size=sm").tooltip("More like this")
        
        with ui.button(icon="share", color="secondary").props("flat size=sm") as view:
            with ui.menu().props("auto-close"):
                with ui.row(wrap=False, align_items="stretch").classes("gap-1 m-0 p-0"):
                    share_button("https://www.reddit.com/submit", REDDIT_ICON).tooltip("Share on Reddit")
                    share_button("https://www.linkedin.com/shareArticle", LINKEDIN_ICON).tooltip("Share on LinkedIn")
                    share_button("https://x.com/intent/tweet", TWITTER_ICON).tooltip("Share on X")
                    share_button("https://wa.me/", WHATSAPP_ICON).tooltip("Share on WhatsApp")
                    # share_button("https://slack.com/share/url", SLACK_ICON).tooltip("Share on Slack") 
        if isinstance(user, User):
            SwitchButton(
                beanops.db.is_bookmarked(user, bean.url), 
                unswitched_text=None, switched_text=None, 
                unswitched_icon="bookmark_outlined", switched_icon="bookmark", 
                on_click=lambda: beanops.toggle_bookmark(user, bean),
                color="secondary"
            ).props("flat size=sm")
    return view  

def render_filter_tags(load_tags: Callable, on_selection_changed: Callable):
    selected_tags = []
    def change_tag_selection(tag: str, selected: bool):        
        selected_tags.append(tag) if selected else selected_tags.remove(tag)
        on_selection_changed(selected_tags) 

    async def render():
        tags = await run.io_bound(load_tags)
        if tags:
            holder.clear()
            with holder:
                [ui.chip(tag, 
                    selectable=True, color="dark", 
                    on_selection_change=lambda e: change_tag_selection(e.sender.text, e.sender.selected)).props("flat filled").classes(" h-full") for tag in tags]
        else:
            holder.delete() 

    # with ui.scroll_area().classes("h-16 p-0 m-0") as view:
    with ui.row().classes("gap-0 p-0 m-0 sm:flex-wrap overflow-x-hidden") as holder:
        ui.skeleton("rect", width="100%").classes("w-full h-full")
    background_tasks.create_lazy(render(), name=f"tags-{now()}")
    # return view
    return holder

def render_pagination(count_items: Callable, on_change: Callable):
    async def render():
        items_count = await run.io_bound(count_items)
        page_count = -(-items_count//MAX_ITEMS_PER_PAGE)
        view.clear()
        if items_count > MAX_ITEMS_PER_PAGE:
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

def render_footer():
    ui.separator().style("height: 5px;").classes("w-full")
    text = "[[Terms of Use](https://github.com/soumitsalman/espresso/blob/main/docs/terms-of-use.md)]   [[Privacy Policy](https://github.com/soumitsalman/espresso/blob/main/docs/privacy-policy.md)]   [[Espresso](https://github.com/soumitsalman/espresso/blob/main/README.md)]   [[Project Cafecito](https://github.com/soumitsalman/espresso/blob/main/docs/project-cafecito.md)]\n\nCopyright © 2024 Project Cafecito. All rights reserved."
    return ui.markdown(text).classes("w-full text-caption text-center")

def render_error_text(msg: str):
    return ui.label(msg).classes("self-center text-center")

def render_card_container(label: str, on_click: Callable = None, header_classes: str = "text-h6"):
    with ui.card(align_items="stretch").tight().props("flat") as panel:        
        holder = ui.item(label, on_click=on_click).classes(header_classes)
        if on_click:
            holder.props("clickable").tooltip("Click for more")
        ui.separator().classes("q-mb-xs") 
    return panel

@contextmanager
def disable_button(button: ui.button):
    button.disable()
    button.props(add="loading")
    try:
        yield
    finally:
        button.props(remove="loading")
        button.enable()

def debounce(func, wait):
    last_call = None
    def debounced(*args, **kwargs):
        nonlocal last_call
        if last_call:
            last_call.cancel()
        last_call = threading.Timer(wait, func, args, kwargs)
        last_call.start()
    return debounced

def _create_navigation_baristas(user: User|str|None):
    items = [
        {
            "icon": "local_cafe_outlined",
            "label": "Following",
            "items": beanops.get_following_baristas(user)
        },
        {
            "icon": "label_outlined",
            "label": "Topics",
            "items": beanops.get_baristas(DEFAULT_TOPIC_BARISTAS)
        },
        {
            "icon": "rss_feed",
            "label": "Outlets",
            "items": beanops.get_baristas(DEFAULT_OUTLET_BARISTAS)
        },
        {
            "icon": "tag",
            "label": "Tags",
            "items": beanops.get_baristas(DEFAULT_TAG_BARISTAS)
        },
        {
            "icon": "scatter_plot",
            "label": "Explore",
            "items": beanops.get_barista_recommendations(user)
        }
        
    ]
    return [item for item in items if item["items"]]