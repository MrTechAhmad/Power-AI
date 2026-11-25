"""Small helpers shared by all pages."""

from datetime import date, datetime

import pandas as pd
import streamlit as st

import config
from database import mongo_db
from database.mongo_db import friendly_error


def money(value):
    return f"{config.CURRENCY} {float(value or 0):,.2f}"


def show_table(df, empty_message="No records found."):
    """Show a DataFrame with readable headers and dates, or a message if empty."""
    if df is None or df.empty:
        st.info(empty_message)
        return
    df = df.copy()
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            # Show only the date unless the column has times in it
            has_time = (df[col].dt.hour + df[col].dt.minute).fillna(0).any()
            df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M" if has_time else "%Y-%m-%d")
    df.columns = [c.replace("_", " ").title() for c in df.columns]
    st.dataframe(df, width="stretch", hide_index=True)


def csv_button(df, file_name, label="Download CSV"):
    if df is not None and not df.empty:
        st.download_button(label, df.to_csv(index=False), file_name=file_name, mime="text/csv")


def show_error(error):
    st.error(friendly_error(error))


def to_date(value):
    """MongoDB stores dates as datetime; forms need a date."""
    if isinstance(value, datetime):
        return value.date()
    return value


def current_user():
    return st.session_state.get("current_user")


def flash(message):
    """Save a success message that survives st.rerun() and shows on the next run."""
    st.session_state["flash_message"] = message


def show_flash():
    message = st.session_state.pop("flash_message", None)
    if message:
        st.success(message)


def mongo_ready():
    """True if MongoDB is running; otherwise shows how to start it."""
    if mongo_db.is_available():
        return True
    st.warning(
        "MongoDB is not running, so AI features are unavailable. "
        "Start the MongoDB service (Windows: Services, then MongoDB Server) and reload the page."
    )
    return False


def today():
    return date.today()
