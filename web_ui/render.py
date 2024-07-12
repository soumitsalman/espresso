from shared import messages, beanops
from pybeansack.datamodels import *
from web_ui.custom_ui import *
from nicegui import ui
from datetime import datetime as dt
from icecream import ic

nugget_markdown = lambda nugget: (f"**{nugget.keyphrase}**"+((": "+nugget.description) if nugget.description else "")) if nugget else None
counter_text = lambda counter: str(counter) if counter < 100 else str(99)+'+'

F_NAME = "header"
F_NUGGETS = "nuggets"
F_SELECTED = "selected"
F_BEANS = "beans"
F_CATEGORIES = "categories"
F_LISTVIEW = "listview"

F_RESPONSE = "response"
F_RESPONSE_BANNER = "response_banner"
F_PROMPT = "prompt"
F_PROCESSING_PROMPT = "processing_prompt"

def render_bean_as_card(bean: Bean):
    if bean:
        with ui.card() as card:
            with ui.row(align_items="center").classes('text-caption'): 
                if bean.created:
                    ui.label(f"📅 {date_to_str(bean.created)}") 
                if bean.source:
                    ui.markdown(f"🔗 [{bean.source}]({bean.url})")   
                if bean.author:
                    ui.label(f"✍️ {bean.author}")
                if bean.noise and bean.noise.comments:
                    ui.label(f"💬 {bean.noise.comments}")
                if bean.noise and bean.noise.likes:
                    ui.label(f"👍 {bean.noise.likes}")
            if bean.tags:
                with ui.row().classes("gap-0"):
                    [ui.chip(word, on_click=lambda : ui.notify(messages.NO_ACTION)).props('outline square') for word in bean.tags[:3]]
            ui.label(bean.title).classes("text-bold")
            ui.markdown(bean.summary)
            
        return card
    
def _render_nugget_body(nugget):
    with ui.row(align_items="center").classes('text-caption'):
        ui.label("📅 "+ date_to_str(nugget.updated))
        ui.chip(nugget.keyphrase, on_click=lambda : ui.notify(messages.NO_ACTION)).classes('text-caption').props('outline square')
    ui.label(text=nugget.description)

def render_nugget_as_card(nugget: Nugget):
    if nugget:
        with ui.card().classes('no-shadow border-[1px]') as card:
            _render_nugget_body(nugget)  
        return card
    
def render_nuggets_as_expandable_list(viewmodel: dict, settings: dict):
    async def load_beans():
        for nugget in (viewmodel[F_NUGGETS] or []):            
            nugget[F_BEANS] = beanops.get_beans_for_nugget(nugget['data'].id, tuple(settings['content_types']), settings['last_ndays'], settings['topn']) if nugget.get(F_SELECTED) else []

    def render_nugget_as_column(nugget: dict):    
        with ui.column().classes("w-full") as item: 
            with HighlightableItem("background-color: lightblue; padding: 15px; border-radius: 4px;") \
                .classes("w-full").bind_highlight_from(nugget, F_SELECTED):                   
                with ui.item_section():
                    _render_nugget_body(nugget['data'])            
                with ui.item_section().props("side"):
                    ui.badge(counter_text(beanops.count_beans_for_nugget(nugget['data'].id, tuple(settings['content_types']), settings['last_ndays'], settings['topn'])))
                    ui.expansion(group="group", on_value_change=load_beans, value=False).bind_value(nugget, F_SELECTED)

            BindableList(render_bean_as_card).classes("w-full").bind_items_from(nugget, F_BEANS)
            ui.separator()
        return item

    return BindableList(render_nugget_as_column).bind_items_from(viewmodel, F_NUGGETS)
    # return BindableTimeline(date_field=lambda nug: nug['data'].updated, header_field=lambda nug: nug['data'].keyphrase, item_render_func=render_nugget_as_timeline_item).props("side=right").bind_items_from(category, "nuggets")

def render_beans_as_list(category: dict, settings: dict):    
    return BindableList(render_bean_as_card).bind_items_from(category, F_BEANS)
