import asyncio
from contextlib import contextmanager
import random
import threading
from typing import Awaitable, Callable
from urllib.parse import urlencode, urljoin
from nicegui import ui, run, app
from app.pybeansack.models import *
from app.shared.utils import *
from app.shared.consts import *
from app.shared.env import *
from app.web.context import *
from app.web import beanops
from app.web.custom_ui import SwitchButton
from icecream import ic

CSS_FILE = "./app/web/styles.css"
SEO_HTML = "./app/web/seo.html"

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

BEAN_META_TAGS = """
<meta name="keywords" content="{tags}">
<meta name="description" content="{description}">
<meta name="robots" content="index, follow">
<meta name="ai-content" content="{description}">
<meta name="ai-intent" content="{tags}">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{description}">
<meta property="og:image" content="{image_url}">
<meta property="og:url" content="{url}">
<meta property="og:type" content="article">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{title}">
<meta name="twitter:description" content="{description}">
<meta name="twitter:image" content="{image_url}">
<link rel="canonical" href="{url}">
<link rel="icon" type="image/x-icon" href="/images/favicon.ico">
<link rel="apple-touch-icon" type="image/png" href="/images/espresso.png">
<meta name="DC.title" content="{title}">
<meta name="DC.description" content="{description}">
<meta name="DC.subject" content="{tags}">
<meta name="DC.creator" content="{creator}">
<meta name="DC.publisher" content="{publisher}">
<meta name="DC.type" content="Article">
"""

PRIMARY_COLOR = "#4e392a"
SECONDARY_COLOR = "#b79579"
IMAGE_DIMENSIONS = "w-32"
STRETCH_FIT = "w-full h-full m-0 p-0"
ACTION_BUTTON_PROPS = "flat size=sm no-caps color=secondary"
TOGGLE_OPTIONS_PROPS = "unelevated rounded no-caps color=dark toggle-color=primary"
SEARCH_BAR_PROPS = "item-aligned standout clearable clear-icon=close maxlength=1000 rounded"
LOGIN_MENU_PROPS = "transition-show=jump-down transition-hide=jump-up"
FILTER_TAGS_BAR_PROPS = "dense shrink no-caps mobile-arrows active-bg-color=primary indicator-color=transparent"
BEANS_GRID_CLASSES = "w-full m-0 p-0 grid-cols-1 bg-transparent"
BEAN_TAG_CLASSES = "ml-0 mr-2 my-0 p-0 text-caption"
FILTER_TAG_CLASSES = "rounded-full bg-dark q-mr-sm"

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

# ellipsis_word = lambda text: text[:MAX_WORD_LENGTH]+'...' if len(text) > MAX_WORD_LENGTH else text
# rounded_number = lambda counter: str(counter) if counter < beanops.MAX_LIMIT else str(beanops.MAX_LIMIT-1)+'+'
# rounded_number_with_max = lambda counter, top: str(counter) if counter <= top else str(top)+'+'

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

def create_share_func(context: Context, bean: Bean, base_url: str):
    url = bean.url if bean.kind != OPED else urljoin(os.getenv("BASE_URL"), create_target("articles", bean.id))
    return lambda: [
        context.log("shared", url=url, target=base_url),
        nav(create_external_target(base_url, url=url, text=f"# {bean.title}\n{bean.summary}\n\n{url}"))
    ]

now = datetime.now
nav = lambda link: ui.navigate.to(link, new_tab=link.startswith("http"))
internal_nav = lambda *args, **kwargs: nav(create_target(*args, **kwargs))
create_external_target = lambda base_url, **kwargs: base_url+"?"+urlencode({key: value for key, value in kwargs.items() if value})

render_banner = lambda text: ui.label(text).classes("text-h5")
render_thick_separator = lambda: ui.separator().props("spaced=false").style("height: 5px;").classes("w-full")
tooltip_msg = lambda ctx, msg: msg if ctx.is_user_registered else f"Login to {msg}"

async def load_and_render_frame(context: Context):
    _, _, nav_panel, _ = render_frame(context)
    await load_navigation_panel(context, nav_panel)

def _render_announcement():
    dismissed = app.storage.user.get("announcement_dismissed", False)
    if dismissed: return None

    def _dismiss_announcement():
        app.storage.user["announcement_dismissed"] = True
        announcement.set_visibility(False)

    with ui.item().classes("w-full justify-between rounded-borders bg-dark py-0") as announcement:
        with ui.item_section().props("avatar"):
            ui.icon("luggage", color="secondary")
        
        with ui.item_section():
            ui.markdown("We Are [Moving](https://beans.cafecito.tech)! But [why](https://espresso-cafecito.ghost.io/espresso-publications/)? Also, now they call me **Beans**.")
        
        with ui.item_section().props("side"):
            ui.button("Dismiss", icon="close", on_click=_dismiss_announcement).props("unelevated rounded size=sm no-caps")
    return announcement

def render_frame(context: Context):
    header, nav_button, nav_panel = render_header(context)
    _render_announcement()
    footer = render_footer(context)
    return header, nav_button, nav_panel, footer

def render_header(context: Context):
    ui.colors(primary=PRIMARY_COLOR, secondary=SECONDARY_COLOR)  
    ui.add_css(CSS_FILE)    
  
    with ui.dialog() as search_dialog, ui.card(align_items="stretch").classes("w-full"):
        render_search_bar(context).classes("fit")      

    nav_panel = ui.left_drawer(bordered=False).props("breakpoint=600 show-if-above").classes("q-pt-xs q-px-sm")
        
    with ui.header(wrap=False).props("reveal").classes("justify-between items-stretch rounded-borders p-1 q-ma-xs") as header:     
        with ui.button(on_click=internal_nav).props("unelevated").classes("q-px-xs"):
            with ui.avatar(square=True, size="md").classes("rounded-borders"):
                ui.image("images/espresso.png")
            ui.label("Beans").classes("q-ml-sm")
            
        nav_button = ui.button(icon="local_cafe_outlined", on_click=nav_panel.toggle).props("unelevated").classes("lt-sm")
        ui.button(icon="search_outlined", on_click=search_dialog.open).props("unelevated").classes("lt-sm")
        render_search_bar(context).props("dense").classes("w-1/2 p-0 gt-xs")

        if context.is_user_registered: render_user_menu(context)
        else: render_login_menu(context)
    return header, nav_button, nav_panel

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

def render_login_menu(context: Context):
    with ui.button(icon="login").props("unelevated") as view:
        with ui.menu().props(LOGIN_MENU_PROPS):           
            for option in LOGIN_OPTIONS:
                with ui.menu_item(option["title"], on_click=lambda url=option['url']: ui.navigate.to(url)):
                    ui.avatar(option["icon"], color="transparent", square=True)
    return view

def render_user_menu(context: Context):
    user = context.user
    with ui.button(icon="perm_identity").props("unelevated") as view:
        with ui.menu().props(LOGIN_MENU_PROPS):
            with ui.item():
                ui.icon("img:"+user.image_url if user.image_url else "person", size="md").classes("q-mr-md").props("avatar")
                ui.label(user.name)
            ui.separator()
                        
            # if beanops.get_page(user.email):
            with ui.menu_item(on_click=lambda: internal_nav("pages", user.email)):
                ui.icon("bookmarks", size="md").classes("q-mr-md")
                with ui.label("Bookmarks"):
                    ui.label("/pages/"+user.email).classes("text-caption")
                                    
            with ui.menu_item(on_click=lambda: ui.notify("Coming soon")):
                ui.icon("settings", size="md").classes("q-mr-md")
                ui.label("Settings")

            ui.separator()
            with ui.menu_item(on_click=lambda: internal_nav("user", "me", "logout")).classes("text-negative"):
                ui.icon("logout", size="md").classes("q-mr-md")
                ui.label("Log Out")
    return view

# render baristas for navigation
async def load_navigation_panel(context: Context, navigation_panel): 
    navigation_items = await run.io_bound(_create_navigation_baristas, context)
    with navigation_panel: 
        with ui.row(wrap=False, align_items="start").classes("gap-0 "+ STRETCH_FIT):

            with ui.tabs().props("vertical outside-arrows mobile-arrows shrink active-bg-color=primary indicator-color=transparent").classes("q-mt-md") as tabs:
                ui.tab("search", label="", icon="search")
                if navigation_items: [ui.tab(item['label'], label="", icon=item['icon']).tooltip(item['label']) for item in navigation_items]
                ui.element("q-route-tab").props("href=/ icon=home_outlined")
            
            with ui.scroll_area().classes(STRETCH_FIT):
                with ui.tab_panels(tabs).props("vertical"):
                    with ui.tab_panel("search").classes(STRETCH_FIT):
                        render_page_search_panel(context)

                    if navigation_items:
                        for item in navigation_items:
                            with ui.tab_panel(item['label']).classes(STRETCH_FIT):
                                render_page_names(context, item['items'], ui.list().classes(STRETCH_FIT))
                        tabs.set_value(navigation_items[0]['label'])
        
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
    with ui.input(placeholder=SEARCH_BEANS_PLACEHOLDER, value=context.query) as search_input:    
        prepend = search_input.add_slot("prepend")   
        with prepend:
            ui.button(icon="search", color="secondary", on_click=trigger_search).bind_visibility_from(search_input, "value").props("round flat dense").classes("m-0")
    search_input.on("keydown.enter", trigger_search).props(SEARCH_BAR_PROPS)
    return search_input

def render_page_search_panel(context: Context):
    async def search_and_render():
        query = search_input.value
        search_results_panel.clear()
        if not query: return 
        context.log("search_page", query=query)
        pages = await run.io_bound(beanops.search_pages, query)
        if pages: render_page_names(context, pages, search_results_panel)
        else:
            with search_results_panel:
                ui.label(NOTHING_FOUND)

    with ui.element() as view:
        search_input = ui.input(placeholder=SEARCH_BARISTA_PLACEHOLDER) \
            .props("dense "+SEARCH_BAR_PROPS) \
            .on("keydown.enter", search_and_render ) \
            .on("clear", search_and_render)
        search_results_panel = ui.list()
        
    return view

def render_page_banner(context: Context):
    if context.is_stored_page: banner_text = context.page.title
    elif context.page_type in [K_RELATED, OPED]: banner_text = context.page.title
    elif context.page_type == K_CATEGORIES: banner_text = f"🏷️ {context.page}"
    elif context.page_type == K_REGIONS: banner_text = f"📍 {context.page}"
    else: banner_text = context.page

    with ui.row(align_items="stretch", wrap=False) as view:
        render_banner(banner_text)
        if context.is_stored_page:
            with ui.button(icon="more_vert").props("flat size=sm"):
                with ui.menu():  
                    # with ui.item("Public"):
                    #     ui.switch(value=barista.public, on_change=lambda: toggle_publish(context)).props("flat checked-icon=public unchecked-icon=public_off")
                    with ui.item("Follow"):
                        ui.switch(value=context.is_following, on_change=lambda: toggle_follow(context)).props("flat checked-icon=playlist_add_check").tooltip(tooltip_msg(context, "Follow")).set_enabled(context.has_follow_permission)
                    with ui.menu_item("Pour a Filtered Cup", on_click=lambda: ui.notify("Coming soon")):
                        ui.avatar(icon="filter_list", color="transparent") 
    return view

async def load_and_render_filter_tags(context: Context, load_items: Callable, on_selection_changed: Callable):
    items = await run.io_bound(load_items)
    return render_filter_tags(context, items, on_selection_changed)

def render_filter_tags(context: Context, items: list|dict, on_selection_changed: Callable):
    if not items: return
    with ui.row(align_items="stretch", wrap=False) as holder:
        with ui.tabs(on_change=lambda e: on_selection_changed([e.sender.value])).props(FILTER_TAGS_BAR_PROPS) as filter_panel:                
            if isinstance(items, list): [ui.tab(item).classes(FILTER_TAG_CLASSES) for item in items]
            elif isinstance(items, dict): [ui.tab(k, label=v).classes(FILTER_TAG_CLASSES) for k, v in items.items()]
            ui.button(icon="close", color="grey-4", on_click=lambda: filter_panel.set_value(None)).props("flat dense round")
    return holder

# async def load_and_render_similar_pages(context: Context):
#     similar_pages = await run.io_bound(beanops.get_page_suggestions, context)
#     return render_page_names(context, similar_pages)

render_page_name = lambda page: ui.item(page.title).props(f"clickable standout href='/pages/{page.id}'").classes("bg-dark rounded-borders")
def render_page_names(context: Context, pages: list[Page], container: ui.element = None):
    if not pages: return
    if not container: return list(map(render_page_name, pages))
    with container: 
        list(map(render_page_name, pages))
    return container

async def load_and_render_page_names(context: Context, load_pages: Callable, container: ui.element = None):           
    pages = await run.io_bound(load_pages, context)
    if container: container.clear()
    render_page_names(context, pages, container)

def render_grid(max_columns: int = 3): 
    classes = BEANS_GRID_CLASSES
    if max_columns == 2: classes += " lg:grid-cols-2"
    elif max_columns == 3: classes += " lg:grid-cols-2 xl:grid-cols-3"
    return ui.grid().classes(classes)

async def load_and_render_beans(context: Context, load_beans: Callable):
    with render_grid() as container:
        beans = await run.io_bound(load_beans)
        if beans: [render_bean_with_related(context, bean).classes(STRETCH_FIT) for bean in beans] 
        else: ui.label(NOTHING_FOUND).classes("w-full text-center") 
    return container

async def load_and_render_beans_as_extendable_list(context: Context, load_beans: Callable):
    current_start = 0   
    async def next_page():
        nonlocal current_start
        with disable_button(more_btn):
            beans = await run.io_bound(load_beans, current_start, config.filters.page.max_beans+1) 
            current_start += config.filters.page.max_beans # moving the cursor no matter what
            if not beans or len(beans) <= config.filters.page.max_beans: more_btn.delete()            
            with beans_panel:
                if beans: [render_bean_with_related(context, bean).classes(STRETCH_FIT) for bean in beans[:config.filters.page.max_beans]]
                else: ui.label(NOTHING_FOUND).classes("w-full text-center") 

    with ui.column() as view:
        beans_panel = render_grid()
        more_btn = ui.button("More Stories", on_click=next_page).props("rounded no-caps icon-right=chevron_right")

    await next_page()
    return view

async def load_and_render_beans_as_paginated_list(context: Context, load_beans: Callable, count_items: Callable):   
    async def next_page(page):
        beans = await run.io_bound(load_beans, (page-1)*config.filters.page.max_beans, config.filters.page.max_beans)   
        beans_panel.clear()
        with beans_panel:
            if beans: [render_bean_with_related(context, bean).classes(STRETCH_FIT) for bean in beans] 
            else: ui.label(NOTHING_FOUND).classes("w-full text-center") 
        return beans
    
    async def page_bar():
        count = await run.io_bound(count_items)
        with bar_panel:
            render_pagination_bar(count, lambda page: next_page(page))
        return count

    with ui.column(align_items="stretch") as panel:
        beans_panel = render_grid()
        bar_panel = ui.element()

    await asyncio.gather(*[next_page(1), page_bar()])
    return panel

def render_bean_with_related(context: Context, bean: Bean):
    related_beans: list[Bean] = None

    def render_bean_as_slide(item: Bean, expanded: bool, on_read: Callable):
        with ui.carousel_slide(item.url).classes("w-full m-0 p-0 no-wrap"):
            render_bean_snapshot(context, item, expanded, on_read)

    async def on_read():
        nonlocal related_beans
        if related_beans: return
        related_beans = await run.io_bound(beanops.get_beans_in_cluster, id=bean.id, kind=None, tags=None, sources=None, last_ndays=None, start=0, limit=config.filters.bean.max_related)
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
            render_bean_summary(context, beanops.load_bean_body(bean))
            body_loaded = True

    with ui.expansion(value=expanded, on_value_change=load_body) \
        .on_value_change(load_body) \
        .on_value_change(on_expanded) \
        .props("dense hide-expand-icon") \
        .classes("rounded-borders " + STRETCH_FIT) as expansion:
        header = expansion.add_slot("header")
        with header:    
            render_bean_header(context, bean).classes(add="p-0")
        if expanded: render_bean_summary(context, bean)
    return expansion

async def load_and_render_whole_bean(context, url):
    bean = await run.io_bound(db.get_bean, url=url, project=beanops.WHOLE_BEAN_FIELDS)
    return render_whole_bean(context, bean), bean

def render_whole_bean(context: Context, bean: Bean):
    if bean.kind == OPED: add_bean_meta_tags(bean)

    with ui.column(align_items="stretch") as view:
        with render_banner(bean.title):
            if bean.kind == OPED: ui.chip("AI Generated", on_click=lambda: internal_nav("sources", bean.source)).props("square").classes("q-mx-sm")
        render_bean_tags(context, bean, truncate=False).classes("gap-2")     
        
        with ui.row(align_items="stretch", wrap=False).classes("w-full flex-col md:flex-row"):
            if bean.image_url: ui.image(bean.image_url).classes("rounded-borders md:w-1/3")
            with ui.column(align_items="stretch").classes("w-full") as view:
                if bean.summary: ui.markdown("> " + bean.summary.strip()).classes("" if bean.kind == OPED else "truncate-multiline")
                # with ui.grid(columns=2).classes("w-full items-center"):
                with ui.row(align_items="center").classes("w-full justify-between"):
                    if bean.kind != OPED: render_read_more(context, bean)
                    render_share_buttons(context, bean)
            
        if bean.kind == OPED:            
            # with render_grid(2 if bean.analysis and bean.insights else 1):
            # with ui.row(align_items="stretch").classes("w-full justify-between"):
            if bean.highlights: 
                with ui.card(align_items="stretch").classes("w-full no-shadow"):  
                    ui.label("Highlights").classes("text-bold text-lg")
                    ui.markdown("\n".join(f"- {point}" for point in bean.highlights))
            if bean.insights: 
                with ui.card(align_items="stretch").classes("w-full no-shadow"):  
                    ui.label("Datapoints").classes("text-bold text-lg")
                    ui.markdown("\n".join(f"- {point}" for point in bean.insights))
            if bean.content: 
                ui.markdown(bean.content)

        if bean.entities: render_bean_entities_as_chips(context, bean)
    return view

add_bean_meta_tags = lambda bean: ui.add_head_html(BEAN_META_TAGS.format(
    title=bean.title,
    description=bean.summary,
    image_url=bean.image_url,
    url=create_target("articles", bean.id),
    tags=", ".join(bean.tags or []),
    creator=bean.author,
    publisher="Cafecito Publications"
))

render_bean_snapshot = render_expandable_bean

def render_bean_header(context: Context, bean: Bean):
    with ui.row(wrap=False, align_items="stretch").classes("w-full bean-header") as view:            
        if bean.image_url: ui.image(bean.image_url).classes(IMAGE_DIMENSIONS)
        with ui.element().classes("w-full"):
            ui.label(bean.title).classes("bean-title")  
            render_bean_tags(context, bean).classes("gap-2 q-my-xs")
    return view

render_tag_as_link = lambda tag, link: ui.link(tag, link, new_tab=link.startswith("http")) \
    .classes("q-mr-md max-w-[30ch] ellipsis") \
    .style("color: secondary; text-decoration: none;")

def render_tag_as_chip(title, target=None, max_width: str = "25ch"): 
    classes = BEAN_TAG_CLASSES
    if max_width: classes += f" max-w-[{max_width}]"
    with ui.chip(
        color="transparent", 
        on_click=(lambda: nav(target)) if target else None
    ).props("dense flat").classes(classes).tooltip(title) as view:
        ui.label(title).classes("ellipsis")
    return view

def render_bean_source_tags(context: Context, bean: Bean):
    with ui.row(align_items="center", wrap=False)as view:
        render_tag_as_chip(naturalday(bean.created))
        render_tag_as_chip(site_name(bean), create_target("sources", bean.source)).props("icon=img:"+favicon(bean))
        if bean.author: render_tag_as_chip(f"✍️ {bean.author}").classes(remove="max-w-[25ch]", add="max-w-[12ch]")
    return view

def render_bean_social_and_classification_tags(context: Context, bean: Bean): 
    with ui.row(align_items="center") as view:    
        if bean.categories: render_tag_as_chip(f"🏷️ {bean.categories[0]}", create_target('categories', bean.categories[0]))         
        if bean.regions: render_tag_as_chip(f"📍 {bean.regions[0]}", create_target('regions', bean.regions[0]))
        # if bean.related: render_attribute_as_chip(f"🗞️ {bean.related}", create_target('related', url=bean.url)).tooltip(f"{bean.related} related article(s)")
        if bean.comments: render_tag_as_chip(f"💬 {naturalnum(bean.comments)}").tooltip(f"{bean.comments} comments across various social media sources")
        if bean.likes: render_tag_as_chip(f"👍 {naturalnum(bean.likes)}").tooltip(f"{bean.likes} likes across various social media sources")
        if bean.shares and bean.shares > 1: render_tag_as_chip(f"🔗 {bean.shares}").tooltip(f"{bean.shares} shares across various social media sources") # another option 🗞️    
    return view

def render_bean_classification_tags(context: Context, bean: Bean): 
    with ui.row(align_items="center", wrap=False) as view:    
        if bean.categories: render_tag_as_chip(f"🏷️ {bean.categories[0]}", create_target('categories', bean.categories[0]))           
        if bean.regions: render_tag_as_chip(f"📍 {bean.regions[0]}", create_target('regions', bean.regions[0]))
    return view

def render_bean_social_tags(context: Context, bean: Bean): 
    with ui.row(align_items="center", wrap=False) as view:    
        if bean.comments: render_tag_as_chip(f"💬 {naturalnum(bean.comments)}").tooltip(f"{bean.comments} comments across various social media sources")
        if bean.likes: render_tag_as_chip(f"👍 {naturalnum(bean.likes)}").tooltip(f"{bean.likes} likes across various social media sources")
        if bean.shares and bean.shares > 1: render_tag_as_chip(f"🔗 {bean.shares}").tooltip(f"{bean.shares} shares across various social media sources") # another option 🗞️
    return view


def render_bean_tags(context: Context, bean: Bean, truncate: bool = True):
    """Renders all bean attributes including publish date, source, author, categories, regions etc."""
    max_width = "25ch" if truncate else None
    with ui.row(align_items="center") as view:
        render_tag_as_chip(naturalday(bean.created), max_width=max_width)
        render_tag_as_chip(site_name(bean), create_target("sources", bean.source), max_width=max_width).props("icon=img:"+favicon(bean))
        
        if bean.author: render_tag_as_chip(f"✍️ {bean.author}", max_width="15ch" if truncate else None)    
        if bean.categories: render_tag_as_chip(f"🏷️ {bean.categories[0]}", create_target('categories', bean.categories[0]), max_width=max_width)         
        if bean.regions: render_tag_as_chip(f"📍 {bean.regions[0]}", create_target('regions', bean.regions[0]), max_width=max_width)
        if bean.chatter:
            if bean.chatter.comments: render_tag_as_chip(f"💬 {naturalnum(bean.chatter.comments)}", max_width=max_width).tooltip(f"{bean.chatter.comments} comments across various social media sources")
            if bean.chatter.likes: render_tag_as_chip(f"👍 {naturalnum(bean.chatter.likes)}", max_width=max_width).tooltip(f"{bean.chatter.likes} likes across various social media sources")
            if bean.chatter.shares and bean.chatter.shares > 1: render_tag_as_chip(f"🔗 {bean.chatter.shares}", max_width=max_width).tooltip(f"{bean.chatter.shares} shares across various social media sources") # another option 🗞️    
    return view

def render_read_more(context: Context, bean: Bean):
    link = create_target("articles", bean.id) if bean.kind == OPED else bean.url
    where = bean.publisher.title or bean.publisher.base_url or bean.source if bean.publisher else bean.source
    return render_tag_as_link("Read More ...", link) \
        .on("click", lambda: context.log("opened", url=link)) \
        .tooltip(f"Read the full article in {where}")

def render_bean_summary(context: Context, bean: Bean):    
    with ui.column(align_items="stretch").classes("w-full h-full") as view:
        if bean.entities: render_bean_entities(context, bean)
        if bean.summary: ui.markdown(bean.summary).classes("bean-body truncate-multiline")
        render_read_more(context, bean)
        render_bean_actions(context, bean).classes(STRETCH_FIT)
    return view

def render_bean_entities_as_chips(context: Context, bean: Bean):
    with ui.row(wrap=True, align_items="baseline").classes("gap-1") as view:
        list(map(
            lambda tag: ui.chip(tag, on_click=lambda tag=tag: internal_nav('entities', tag)), 
            random.sample(bean.entities, min(config.filters.page.max_tags, len(bean.entities)))
        ))
    return view

def render_bean_entities(context: Context, bean: Bean):    
    with ui.row(wrap=True, align_items="baseline").classes("gap-0 m-0 p-0 text-caption") as view:
        list(map(
            lambda ent: render_tag_as_link(ent, create_target("entities", ent)), 
            random.sample(bean.entities, min(config.filters.bean.max_entities, len(bean.entities)))
        ))
    return view

def render_bean_actions(context: Context, bean: Bean): 
    bug_report = render_report_a_bug()

    # async def open_read():
    #     context.log("opened", url=bean.url)
    #     if bean.kind == OPED: internal_nav("articles", bean.url)
    #     else: nav(bean.url, new_tab=True)

    async def show_bug_report():
        issue = await bug_report
        if issue: context.log("reported", url=bean.url, bug=issue)

    with ui.row(wrap=False, align_items="center").classes("justify-between") as view:
        with ui.button_group().props(ACTION_BUTTON_PROPS).classes("p-0 m-0"):
            # ui.toggle(options=["liked", "disliked"], on_change=lambda e: context.log(e.sender.value, url=bean.url)).props(ACTION_BUTTON_PROPS)
            ui.button(icon="thumb_up", color="secondary", on_click=lambda: context.log("liked", url=bean.url)) \
                .props(ACTION_BUTTON_PROPS) \
                .tooltip("Show more of these")
            
            ui.button(icon="thumb_down", color="secondary", on_click=lambda: context.log("disliked", url=bean.url)) \
                .props(ACTION_BUTTON_PROPS) \
                .tooltip("Show less of these")
            
            ui.button(icon="bug_report", color="secondary", on_click=show_bug_report) \
                .props(ACTION_BUTTON_PROPS) \
                .tooltip("Report Bug")
            
            # ui.checkbox(value=False, on_change=lambda: toggle_bookmark(context, bean)) \
            #     .props("unchecked-icon=bookmark_outlined checked-icon=bookmark size=xs") \
            #     .tooltip(tooltip_msg(context, "Bookmark")) \
                # .set_enabled(context.is_user_registered)

        with ui.button_group().props(ACTION_BUTTON_PROPS).classes("p-0 m-0"):
            # icon = "auto_stories" "read_more" "eyeglasses" "search"
            # ui.button(icon="auto_stories", on_click=open_read).props(ACTION_BUTTON_PROPS).tooltip("Read the full article") 
            if bean.kind != OPED: ui.button(icon="auto_stories", on_click=lambda: internal_nav("related", url=bean.url)).props(ACTION_BUTTON_PROPS).tooltip("More like this")
            with ui.button(icon="share").props(ACTION_BUTTON_PROPS):
                with ui.menu().props("auto-close"):
                    render_share_buttons(context, bean).classes("gap-1 m-0 p-0")
                       
    return view  

render_share_button = lambda context, bean, base_url, icon: ui.button(on_click=create_share_func(context, bean, base_url), icon=icon, color="transparent")

def render_share_buttons(context: Context, bean: Bean):
    with ui.button_group().props(ACTION_BUTTON_PROPS) as buttons:
        render_share_button(context, bean, "https://www.reddit.com/submit", REDDIT_ICON).tooltip("Share on Reddit")
        render_share_button(context, bean, "https://www.linkedin.com/shareArticle", LINKEDIN_ICON).tooltip("Share on LinkedIn")
        render_share_button(context, bean, "https://x.com/intent/tweet", TWITTER_ICON).tooltip("Share on X")
        render_share_button(context, bean, "https://wa.me/", WHATSAPP_ICON).tooltip("Share on WhatsApp")
        # render_share_button("https://slack.com/share/url", SLACK_ICON).tooltip("Share on Slack") 
    return buttons

def render_report_a_bug():
    with ui.dialog() as dialog, ui.card():
        with ui.row(wrap=False):
            ui.icon("bug_report")
            ui.label("Don't like it? Report it!")
        with ui.row():
            ui.button("Category/Scope WTF", on_click=lambda: dialog.submit("Category/Scope WTF"))
            # ui.button("Summary/Title WTF", on_click=lambda: dialog.submit("Summary/Title WTF"))
            ui.button("Ugly AF", on_click=lambda: dialog.submit("Ugly AF"))
        other_text = ui.input(placeholder="Cry me a river").props("standout").classes("w-full")
        with ui.row(wrap=False).classes("self-end"):
            ui.button("Report", on_click=lambda: dialog.submit(other_text.value)).bind_visibility_from(other_text, "value", lambda v: v and len(v.split()) >=3)
            ui.button("Cancel", color="negative", on_click=lambda: dialog.submit(False))
    return dialog

async def render_pagination_bar(count_items: Callable, on_change: Callable):
    async def render():
        items_count = await run.io_bound(count_items)
        page_count = -(-items_count//config.filters.page.max_beans)
        view.clear()
        if items_count > config.filters.page.max_beans:
            with view:
                ui.pagination(min=1, max=page_count, direction_links=True, on_change=lambda e: on_change(e.sender.value)).props("max-pages=10 ellipses")            

    with ui.element() as view:
        ui.skeleton("rect", width="100%").classes("w-full")
        await render()
    # background_tasks.create_lazy(render(), name=f"pagination-{now()}")
    return view

def render_pagination_bar(items_count: int, on_change: Callable):
    if items_count <= config.filters.page.max_beans: return # no need render anything
    page_count = -(-items_count//config.filters.page.max_beans)
    return ui.pagination(value=1, min=1, max=page_count, direction_links=True, on_change=lambda e: on_change(e.sender.value)).props("max-pages=10 ellipses")

def render_skeleton_beans(count: int = 3, container: ui.element = None):
    container = container or ui.list()
    with container:
        for _ in range(count):
            with ui.item().classes("w-full"):
                with ui.item_section().props("side"):
                    ui.skeleton("rect", size="8em")
                with ui.item_section().props("top"):
                    ui.skeleton("text", width="100%")
                    ui.skeleton("text", width="100%")
                    ui.skeleton("text", width="40%")
    return container

def render_skeleton_page_names(count = 3):
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
    if not context.is_user_registered: return False

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
            "items": db.get_following_pages(context.user, beanops.PAGE_DEFAULT_FIELDS) if context.is_user_registered else None
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