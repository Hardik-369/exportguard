# ExportGuard — Looker Studio Dashboard Guide

## Step 0: Open Looker Studio

1. Go to https://lookerstudio.google.com/
2. Sign in with the same Google account used for your Cloud project
3. Click **"Create"** (blue button, top-left) → **"Report"**
4. A new blank report opens with an "Add data to report" panel on the right

---

## Step 1: Add BigQuery as a Data Source

In the right-side panel **"Add data to report"**:

1. Click **"BigQuery"** from the list of connectors
2. Under **"Select a project"** → click on **"quixotic-carver-418112"**
3. Under **"Select a dataset"** → click on **"exportguard"**
4. You'll see a list of tables and views
5. Find **"buyer_risk_summary"** (look for the VIEW badge) → click it → click **"Add"** (bottom-right)
6. A popup says "Add to report" → click **"Add to report"**

You should now see a table of data on your report canvas.

---

## Step 2: Create Chart 1 — Buyer Risk Leaderboard

1. Click anywhere on the **blank canvas** (outside the auto-generated table) to deselect
2. In the top toolbar, click **"Add a chart"** (or the chart icon in the toolbar)
3. Choose **"Bar chart"** from the dropdown
4. A bar chart appears on the canvas

### Configure the chart:

On the right panel, go to the **"Setup"** tab (not Style):

| Field | What to do |
|---|---|
| **Data Source** | Should already say `buyer_risk_summary` |
| **Dimension** | Click the current dimension → search and select **`buyer_id`** |
| **Metric** | Click the current metric → search and select **`risk_score`** |
| **Sort** | Click the sort dropdown under the metric → select **`risk_score` → Descending** |
| **Default date range** | Click it → select **"Auto"** |

### Add a breakdown dimension (for colors):

1. Under **"Breakdown dimension"** (just below the metric), click **"Add"** or **"+"**
2. Search and select **`risk_category`**

### Filter to Top 20:

1. Scroll down in the Setup panel to **"Filters"**
2. Click **"Add a filter"** → **"Create filter"**
3. A popup opens:
   - **Filter name:** `Top 20 Buyers`
   - **Include / Exclude:** Keep as **Include**
   - **Dimension:** search and select **`buyer_id`**
   - **Condition:** scroll and choose **"Is in the top N"**
   - **N:** type `20`
   - Click **"Save"**
4. The filter is now applied

### Set the title:

1. Go to the **"Style"** tab (next to Setup)
2. Scroll to **"Chart header"** section
3. In the **"Title"** box, type: `Top 20 Buyers by Risk Score`
4. Optionally, increase font size to `16`

### Resize and position:

- Drag the chart to the **top-left** area
- Drag the bottom-right corner to make it about **half the page width**

---

## Step 3: Add a Second Data Source

1. Click **"Add data"** in the top-right toolbar (or Resource → Manage added data sources)
2. Click **"Add a data source"**
3. Select **"BigQuery"** again
4. Navigate: `quixotic-carver-418112` → `exportguard` → **`country_risk_trend`** → **"Add"** → **"Add to report"**

---

## Step 4: Create Chart 2 — Country Risk Over Time

1. Click the blank canvas to deselect
2. **"Add a chart"** → choose **"Time series chart"** (look for the line chart icon)
3. A time series chart appears

### Configure:

In the **Setup** tab:

| Field | What to do |
|---|---|
| **Data Source** | Select **`country_risk_trend`** from the dropdown |
| **Date range dimension** | Click it → search and select **`month`** |
| **Dimension** | Leave as `month` (auto-filled) |
| **Breakdown dimension** | Click **"Add"** → search and select **`country`** |
| **Metric** | Click current metric → search and select **`composite_risk_index`** |
| **Sort** | Click the sort under the metric → **`month` → Ascending** |
| **Default date range** | **"Auto"** |

### Filter to Top 10 countries:

1. Under **"Filters"**, click **"Add a filter"** → **"Create filter"**
2. **Filter name:** `Top 10 Countries`
3. **Include / Exclude:** **Include**
4. **Dimension:** **`country`**
5. **Condition:** **"Is in the top N"**
6. **N:** `10`
7. **"Save"**

### Set title:

1. **Style** tab → **Chart header** → **Title:** `Country Risk Index Over Time`
2. Set font size to `16`

### Resize and position:

- Drag to the **top-right** (next to the bar chart)
- Make it the same size as the left chart

---

## Step 5: Add Third Data Source

1. **"Add data"** → **"Add a data source"** → **BigQuery**
2. Navigate: `quixotic-carver-418112` → `exportguard` → **`shipment_outcomes_by_hs_code`** → **"Add"** → **"Add to report"**

---

## Step 6: Create Chart 3 — HS-code Exposure Breakdown

1. Click blank canvas to deselect
2. **"Add a chart"** → choose **"Stacked bar chart"** (under Bar)
3. A stacked bar chart appears

### Configure:

**Setup** tab:

| Field | What to do |
|---|---|
| **Data Source** | **`shipment_outcomes_by_hs_code`** |
| **Dimension** | **`product_category`** |
| **Metric** | **`total_value_usd`** |
| **Sort** | Click the sort under the metric → **`total_value_usd` → Descending** |
| **Default date range** | **"Auto"** |

### Set title:

1. **Style** → **Chart header** → **Title:** `Shipment Value by Product Category`
2. Font size `16`

### Resize and position:

- Drag to the **bottom**, spanning the **full width** of the page
- Make it about half the page height

---

## Step 7: Add a Report Title

1. Click **"Add a text box"** (toolbar: `T` icon, or Insert → Text box)
2. A text box appears — type: `ExportGuard — Trade Risk Dashboard`
3. In the right **Style** panel:
   - Font: **Inter** or **Arial**
   - Size: `24` or `28`
   - Bold: **On**
4. Drag the text box to the **top-center** of the report page

---

## Step 8: Arrange the Layout

Your dashboard should look like this:

```
┌─────────────────────────────────────────────────┐
│          ExportGuard — Trade Risk Dashboard       │
├──────────────────────────┬──────────────────────┤
│                          │                       │
│  Top 20 Buyers           │  Country Risk Index   │
│  by Risk Score            │  Over Time            │
│  (bar chart)             │  (line chart)         │
│                          │                       │
├──────────────────────────┴──────────────────────┤
│                                                  │
│  Shipment Value by Product Category              │
│  (stacked bar chart, full width)                 │
│                                                  │
└─────────────────────────────────────────────────┘
```

Tips:
- Click on a chart and use the **arrow keys** for fine positioning
- Drag the **edges** of charts to resize them
- Use **"View" → "Fit to width"** to see the full dashboard

---

## Step 9: Share the Dashboard

1. Click **"Share"** (top-right, blue button)
2. Click **"Manage access"**
3. Set **"Anyone with the link"** → **"Viewer"** (or keep it restricted)
4. Copy the URL from the browser address bar — this is your dashboard link

---

## Troubleshooting

| Problem | Fix |
|---|---|
| **Can't find BigQuery connector** | Click "See all connectors" and search "BigQuery" |
| **Can't see views** | In the BigQuery data picker, make sure you're looking at the right project + dataset. Views show with a **VIEW** badge |
| **Chart shows "No data"** | Go to **Resource** → **Manage added data sources** → edit the data source → check credentials |
| **Filter not working** | Make sure the dimension name matches exactly (`buyer_id`, not `id`) |
| **Can't find "Breakdown dimension"** | It's in the **Setup** tab, right below the metric field |
| **Charts overlap** | Click the "Arrange" menu → "Distribute" or manually drag to separate |
