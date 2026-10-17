"""Small helpers so the app also runs on slightly older Streamlit versions."""
import streamlit as st
from streamlit.errors import StreamlitAPIException


def _call(fn, args, kwargs, tries):
    last = None
    for extra in tries:
        try:
            return fn(*args, **kwargs, **extra)
        except (TypeError, StreamlitAPIException) as e:   # this Streamlit version doesn't know that option
            last = e
    raise last


def _stretch():
    return [{"width": "stretch"}, {"use_container_width": True}, {}]


def data_editor(*args, **kwargs):
    return _call(st.data_editor, args, kwargs, _stretch())


def altair_chart(*args, **kwargs):
    return _call(st.altair_chart, args, kwargs, _stretch())


def dataframe(*args, fit=False, **kwargs):
    tries = [{"width": "content"}, {}] if fit else _stretch()
    return _call(st.dataframe, args, kwargs, tries)
