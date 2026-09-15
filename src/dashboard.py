import os
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


# ============================================================
# LOAD DATA
# ============================================================

def load_dataset(filepath):
    extension = os.path.splitext(filepath)[1].lower()

    if extension == ".csv":
        return pd.read_csv(filepath)

    if extension in {".xlsx", ".xls"}:
        return pd.read_excel(filepath)

    raise ValueError("Dashboard supports CSV and Excel files.")


# ============================================================
# HELPERS
# ============================================================

def _clean_columns(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _numeric(df):
    return list(df.select_dtypes(include="number").columns)


def _categorical(df):
    return list(df.select_dtypes(include=["object", "category", "bool"]).columns)


def _find_column(df, names):
    lowered = {str(c).lower(): c for c in df.columns}

    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]

    for c in df.columns:
        cl = str(c).lower()
        if any(name.lower() in cl for name in names):
            return c

    return None


def _currency(value):
    return f"${value:,.2f}"


def _make_kpis(df):
    nums = _numeric(df)
    kpis = []

    order_col = _find_column(df, [
        "order_id", "order id", "orderid", "transaction_id"
    ])
    quantity_col = _find_column(df, [
        "quantity", "units", "units_sold", "qty"
    ])
    price_col = _find_column(df, [
        "price", "unit_price", "unit price", "revenue", "sales"
    ])
    delivery_days_col = _find_column(df, [
        "estimated_days_to_deliver", "delivery_days",
        "delivery time", "days_to_deliver"
    ])
    delivery_fee_col = _find_column(df, [
        "delivery_charge", "delivery fee", "shipping_cost",
        "shipping", "delivery_cost"
    ])

    # Total Orders
    if order_col:
        value = int(df[order_col].nunique())
        kpis.append(("Total Orders", f"{value:,}", "Unique orders"))
    else:
        value = len(df)
        kpis.append(("Total Rows / Orders", f"{value:,}", "Rows in dataset"))

    # Total Units
    if quantity_col:
        value = df[quantity_col].sum()
        kpis.append(("Total Units Sold", f"{value:,.0f}", "Sum of quantity"))

    # Average Price
    if price_col:
        value = df[price_col].mean()
        kpis.append(("Average Price", _currency(value), f"Mean of {price_col}"))

    # Average delivery time
    if delivery_days_col:
        value = df[delivery_days_col].mean()
        kpis.append(("Avg Delivery Time", f"{value:.1f} days", f"Mean of {delivery_days_col}"))

    # Total delivery fees
    if delivery_fee_col:
        value = df[delivery_fee_col].sum()
        kpis.append(("Total Delivery Fees", _currency(value), f"Sum of {delivery_fee_col}"))

    # Fill up to 5 cards with useful numeric summaries
    for col in nums:
        if len(kpis) >= 5:
            break
        if any(col.lower() in item[2].lower() for item in kpis):
            continue
        value = df[col].mean()
        kpis.append((f"Avg {col}", f"{value:,.2f}", f"Mean of {col}"))

    return kpis[:5]


def _figure_layout(fig):
    fig.update_layout(
        template="plotly_white",
        title_font=dict(size=20),
        margin=dict(l=40, r=30, t=70, b=50),
        height=400,
        legend=dict(orientation="h", y=-0.2),
    )
    return fig


# ============================================================
# AUTOMATIC DASHBOARD
# ============================================================

def create_dashboard(filepath, chart_type="auto", x_column="", y_column=""):
    """
    Build a complete dashboard from an Excel/CSV file.

    Returns:
        {
            "dataframe": df,
            "kpis": [(title, value, description), ...],
            "figures": [plotly figures],
            "insights": [str, ...],
            "title": str
        }
    """

    df = _clean_columns(load_dataset(filepath))

    if df.empty:
        raise ValueError("The uploaded dataset is empty.")

    numeric_columns = _numeric(df)
    categorical_columns = _categorical(df)

    kpis = _make_kpis(df)
    figures = []
    insights = []

    # --------------------------------------------------------
    # 1. Categorical vs numeric -> best grouped bar chart
    # --------------------------------------------------------
    city_col = _find_column(df, [
        "city", "region", "state", "country", "category",
        "product_category", "department"
    ])

    value_col = _find_column(df, [
        "revenue", "sales", "price", "profit", "amount",
        "delivery_charge", "quantity"
    ])

    # Only aggregate a numeric column. A text column here makes
    # groupby().sum() concatenate strings and the formatted insight crash.
    if value_col is not None and value_col not in numeric_columns:
        value_col = None

    if value_col is None and numeric_columns:
        value_col = numeric_columns[0]

    if city_col and value_col:
        grouped = (
            df.groupby(city_col, dropna=False)[value_col]
            .sum()
            .sort_values(ascending=False)
            .head(15)
            .reset_index()
        )

        fig = px.bar(
            grouped,
            x=city_col,
            y=value_col,
            title=f"{value_col} by {city_col}",
            text_auto=".2s",
        )
        figures.append(_figure_layout(fig))

        if not grouped.empty:
            top = grouped.iloc[0]
            insights.append(
                f"{top[city_col]} has the highest total {value_col} "
                f"({top[value_col]:,.2f})."
            )

    # --------------------------------------------------------
    # 2. Gender/category distribution -> donut
    # --------------------------------------------------------
    gender_col = _find_column(df, [
        "gender", "sex", "customer_type", "segment"
    ])

    if gender_col:
        counts = (
            df[gender_col]
            .astype("object")
            .fillna("Unknown")
            .value_counts()
            .head(10)
            .reset_index()
        )
        counts.columns = [gender_col, "Count"]

        fig = px.pie(
            counts,
            names=gender_col,
            values="Count",
            hole=0.55,
            title=f"Order Distribution by {gender_col}",
        )
        figures.append(_figure_layout(fig))

    elif categorical_columns:
        col = categorical_columns[0]
        counts = (
            df[col].astype("object").fillna("Unknown")
            .value_counts()
            .head(10)
            .reset_index()
        )
        counts.columns = [col, "Count"]

        fig = px.pie(
            counts,
            names=col,
            values="Count",
            hole=0.55,
            title=f"Distribution of {col}",
        )
        figures.append(_figure_layout(fig))

    # --------------------------------------------------------
    # 3. Numeric relationship -> scatter
    # --------------------------------------------------------
    if len(numeric_columns) >= 2:
        x_num = numeric_columns[0]
        y_num = numeric_columns[1]

        # Prefer price vs quantity when available
        price = _find_column(df, ["price", "unit_price"])
        quantity = _find_column(df, ["quantity", "qty", "units"])

        if price and quantity:
            x_num, y_num = price, quantity

        fig = px.scatter(
            df,
            x=x_num,
            y=y_num,
            title=f"{y_num} vs {x_num}",
            opacity=0.7,
        )
        figures.append(_figure_layout(fig))

    # --------------------------------------------------------
    # 4. Delivery / numeric distribution -> histogram
    # --------------------------------------------------------
    distribution_col = _find_column(df, [
        "estimated_days_to_deliver", "delivery_days",
        "age", "price", "quantity"
    ])

    if not distribution_col and numeric_columns:
        distribution_col = numeric_columns[0]

    if distribution_col:
        fig = px.histogram(
            df,
            x=distribution_col,
            nbins=15,
            title=f"Distribution of {distribution_col}",
        )
        figures.append(_figure_layout(fig))

    # --------------------------------------------------------
    # 5. Coupon / categorical frequency
    # --------------------------------------------------------
    coupon_col = _find_column(df, [
        "coupon_code", "coupon", "discount_code", "promo_code"
    ])

    if coupon_col:
        counts = (
            df[coupon_col]
            .astype("object")
            .fillna("No Coupon")
            .value_counts()
            .head(15)
            .reset_index()
        )
        counts.columns = [coupon_col, "Count"]

        fig = px.bar(
            counts,
            x=coupon_col,
            y="Count",
            title="Coupon Usage",
            text_auto=True,
        )
        figures.append(_figure_layout(fig))

    # --------------------------------------------------------
    # 6. Age distribution if available
    # --------------------------------------------------------
    age_col = _find_column(df, ["age", "customer_age"])

    if age_col:
        fig = px.histogram(
            df,
            x=age_col,
            nbins=15,
            title="Customer Age Distribution",
        )
        figures.append(_figure_layout(fig))

        avg_age = df[age_col].mean()
        insights.append(f"Average customer age is approximately {avg_age:.1f} years.")

    # --------------------------------------------------------
    # 7. Date trend if a date column exists
    # --------------------------------------------------------
    date_col = _find_column(df, [
        "date", "order_date", "order date", "transaction_date",
        "created_at", "month"
    ])

    if date_col:
        temp = df.copy()
        temp[date_col] = pd.to_datetime(temp[date_col], errors="coerce")
        temp = temp.dropna(subset=[date_col])

        if not temp.empty and value_col:
            trend = (
                temp.groupby(temp[date_col].dt.to_period("M"))[value_col]
                .sum()
                .reset_index()
            )
            trend[date_col] = trend[date_col].astype(str)

            fig = px.line(
                trend,
                x=date_col,
                y=value_col,
                markers=True,
                title=f"Monthly {value_col} Trend",
            )
            figures.append(_figure_layout(fig))

    # --------------------------------------------------------
    # Generic insight
    # --------------------------------------------------------
    insights.insert(
        0,
        f"Dataset contains {len(df):,} rows and {len(df.columns):,} columns."
    )

    if numeric_columns:
        insights.append(
            f"Numeric analysis is available for: "
            f"{', '.join(map(str, numeric_columns[:6]))}."
        )

    # Avoid an excessive number of charts
    figures = figures[:6]

    return {
        "dataframe": df,
        "kpis": kpis,
        "figures": figures,
        "insights": insights[:6],
        "title": "📊 Automated Business Analytics Dashboard",
        # Backward compatibility for code expecting one figure
        "figure": figures[0] if figures else None,
        "chart_type": "auto",
        "x_column": x_column,
        "y_column": y_column,
    }


# ============================================================
# OPTIONAL SINGLE-CHART API
# ============================================================

def create_single_chart(filepath, chart_type="auto", x_column="", y_column=""):
    df = _clean_columns(load_dataset(filepath))

    numeric_columns = _numeric(df)
    categorical_columns = _categorical(df)

    if not x_column:
        x_column = categorical_columns[0] if categorical_columns else (
            df.columns[0] if len(df.columns) else ""
        )

    if not y_column and numeric_columns:
        y_column = numeric_columns[0]

    chart_type = (chart_type or "auto").lower()

    if chart_type == "histogram":
        if not y_column:
            raise ValueError("Histogram requires a numeric column.")
        figure = px.histogram(df, x=y_column, title=f"Distribution of {y_column}")

    elif chart_type == "bar":
        if not x_column or not y_column:
            raise ValueError("Bar chart requires x and y columns.")
        figure = px.bar(df, x=x_column, y=y_column, title=f"{y_column} by {x_column}")

    elif chart_type == "scatter":
        if not x_column or not y_column:
            raise ValueError("Scatter chart requires x and y columns.")
        figure = px.scatter(df, x=x_column, y=y_column, title=f"{y_column} vs {x_column}")

    elif chart_type == "line":
        if not x_column or not y_column:
            raise ValueError("Line chart requires x and y columns.")
        figure = px.line(df, x=x_column, y=y_column, title=f"{y_column} over {x_column}")

    elif chart_type == "pie":
        if not x_column:
            raise ValueError("Pie chart requires a categorical column.")
        counts = df[x_column].value_counts().head(10).reset_index()
        counts.columns = [x_column, "count"]
        figure = px.pie(
            counts,
            names=x_column,
            values="count",
            title=f"Distribution of {x_column}",
        )

    else:
        result = create_dashboard(filepath)
        figure = result["figure"]

        if figure is None:
            raise ValueError("Could not create a suitable chart.")

    return {
        "figure": _figure_layout(figure),
        "dataframe": df,
        "chart_type": chart_type,
        "x_column": x_column,
        "y_column": y_column,
    }