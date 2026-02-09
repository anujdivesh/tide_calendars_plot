from matplotlib import pyplot as plt
import datetime
import calendar
from pathlib import Path
import math
import matplotlib.dates as mdates
import matplotlib as mpl

def cm2inch(*tupl):
    inch = 2.54
    if type(tupl[0]) == tuple:
        return tuple(i/inch for i in tupl[0])
    else:
        return tuple()


def load_tide_extrema(file_path: Path):
    points = []
    if not file_path.exists():
        return points
    with file_path.open('r', encoding='utf-8', errors='ignore') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 2:
                continue
            try:
                dt = datetime.datetime.fromisoformat(parts[0])
                height = float(parts[1])
            except Exception:
                continue
            phase = ''
            if len(parts) >= 3 and parts[2]:
                phase = parts[2].strip()[:1].upper()
            points.append((dt, height, phase))
    points.sort(key=lambda x: x[0])
    return points


def cosine_interp(t, t0, t1, y0, y1):
    """Smooth (sinusoid-like) interpolation between extrema."""
    total = (t1 - t0).total_seconds()
    if total <= 0:
        return y0
    frac = (t - t0).total_seconds() / total
    if frac <= 0:
        return y0
    if frac >= 1:
        return y1
    mid = 0.5 * (y0 + y1)
    amp = 0.5 * (y0 - y1)
    return mid + amp * math.cos(math.pi * frac)

figsize = cm2inch((21,29.7))
fig, ax = plt.subplots(figsize=figsize, dpi=120)
ax.axis('off')

# Draw day cards for the current month, aligned under weekday headings
# Set these to render a specific month (e.g., YEAR=2027, MONTH=1). Leave as None to use current month.
YEAR = 2025
MONTH = 2

today = datetime.date.today()
year = YEAR if YEAR is not None else today.year
month = MONTH if MONTH is not None else today.month


# Calculate positions in figure coordinates
fig_width_cm, fig_height_cm = 21, 29.7
top_whitespace_cm = 0.0  # full top coverage for header
header_height_cm = 2

# Convert cm to figure fraction
top_whitespace_frac = top_whitespace_cm / fig_height_cm
header_height_frac = header_height_cm / fig_height_cm


# Calculate horizontal gaps (1.5cm on each side for table/label area)
label_side_gap_cm = 1.5
label_side_gap_frac = label_side_gap_cm / fig_width_cm
label_area_width_frac = 1 - 2 * label_side_gap_frac

# Header uses full width
header_side_gap_cm = 0.0
header_side_gap_frac = header_side_gap_cm / fig_width_cm
header_width_frac = 1 - 2 * header_side_gap_frac

# Draw grey header rectangle (centered, not full width)
fig.patches.extend([
    plt.Rectangle(
        (header_side_gap_frac, 1 - top_whitespace_frac - header_height_frac),
        header_width_frac, header_height_frac,
        transform=fig.transFigure, figure=fig,
        color='#666666', zorder=1
    )
])

# Add white title text aligned with the calendar/charts left edge
fig.text(
    label_side_gap_frac, 1 - top_whitespace_frac - header_height_frac/2 - (0.4 / fig_height_cm),
    'TIDAL PREDICTIONS FOR SUVA',
    ha='left', va='center',
    color='white', fontsize=18, weight='bold', zorder=2
)


# Add a small, lighter grey area below the header
light_grey_height_cm = 0.9  # Small height
light_grey_height_frac = light_grey_height_cm / fig_height_cm
light_grey_bottom_frac = 1 - top_whitespace_frac - header_height_frac - light_grey_height_frac

fig.patches.extend([
    plt.Rectangle(
        (header_side_gap_frac, light_grey_bottom_frac),
        header_width_frac, light_grey_height_frac,
        transform=fig.transFigure, figure=fig,
        color='#f0f0f0', zorder=1.5
    )
])

# Month + year label in the light grey strip (full month name)
month_label = f"{calendar.month_name[month]} {year}".upper()
fig.text(
    label_side_gap_frac,
    light_grey_bottom_frac + light_grey_height_frac - (0.30 / fig_height_cm),
    month_label + "     Local Standard Time",
    ha='left', va='top',
    color='#111111', fontsize=12, weight='bold', zorder=2
)

# Place weekday labels below the lighter grey area, within 2cm side margins


labels = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]
num_labels = len(labels)
label_y = light_grey_bottom_frac - 0.025  # a little below the light grey area
cell_width_frac = label_area_width_frac / num_labels
for i, label in enumerate(labels):
    # Center label above each table cell
    x = label_side_gap_frac + (i + 0.5) * cell_width_frac
    fig.text(
        x, label_y,
        label,
        ha='center', va='top',
        color='#444', fontsize=9.5, weight='bold', zorder=3
    )


# Calendar layout (Sunday as first column)
_first_weekday_mon0, num_days = calendar.monthrange(year, month)  # Monday=0

# Build weeks Sunday-first; 0 means "no day"
weeks = calendar.Calendar(firstweekday=6).monthdayscalendar(year, month)

# If the last week is sparse, optionally move its days into the leading blanks
# of week 1 (e.g., Jan 2027: move 31 into the first Sunday slot) and drop the
# last week. Only do this if at least one leading blank remains afterward.
if weeks:
    first_week = list(weeks[0])
    last_week = list(weeks[-1])

    leading_zeros = 0
    for d in first_week:
        if d == 0:
            leading_zeros += 1
        else:
            break

    last_days = [d for d in last_week if d != 0]
    required_empty_after = 1
    max_movable = max(0, leading_zeros - required_empty_after)
    if max_movable > 0 and 0 < len(last_days) <= max_movable:
        for idx, d in enumerate(last_days):
            first_week[idx] = d
        weeks = [first_week] + weeks[1:-1]

num_rows = len(weeks)

# Card geometry
card_height_cm = 3.5

# Vertical gap between week rows (increase to create space above x-axis labels)
row_gap_y_cm = 0.6
row_gap_y_frac = row_gap_y_cm / fig_height_cm

label_table_gap_frac = 0.015
cards_top_y = label_y - label_table_gap_frac
bottom_margin_frac = 0.06
available_height_frac = cards_top_y - bottom_margin_frac

max_card_height_frac = (available_height_frac - (num_rows - 1) * row_gap_y_frac) / max(1, num_rows)
card_height_frac = min(card_height_cm / fig_height_cm, max_card_height_frac)

# Split line inside the card (1.5cm from top, but clamp if cards are shorter)
line_offset_cm_target = 1.5
card_height_cm_effective = card_height_frac * fig_height_cm
line_offset_cm = min(line_offset_cm_target, card_height_cm_effective * 0.7)
line_offset_frac = line_offset_cm / fig_height_cm

# Mini-grid style
x_ticks = [0, 6, 12, 18, 24]
y_ticks = [0, 1, 2, 3]
xticklabels = ["0", "6", "12", "18", "0"]
yticklabels = ["0", "1", "2", "3"]
grid_color = '#d0d0d0'
grid_lw = 0.6
grid_alpha = 1.0

# Tide data file (same folder as this script)
DATA_FILE = '66840_hlw.data'
tide_points = load_tide_extrema(Path(__file__).with_name(DATA_FILE))

# Group tide extrema by day for listing in the card header area
tide_events_by_day = {}
for dt, height, phase in tide_points:
    if dt.year != year or dt.month != month:
        continue
    tide_events_by_day.setdefault(dt.day, []).append((dt, height, phase))

for day, events in tide_events_by_day.items():
    events.sort(key=lambda x: x[0])

# For axis labels: show x/y labels on the leftmost visible card in each row
row_leftmost_col = {}
for r, wk in enumerate(weeks):
    cols = [c for c, d in enumerate(wk) if d != 0]
    if cols:
        row_leftmost_col[r] = min(cols)

# Store mini-grid boxes per day for plotting (figure coords)
day_boxes = {}

for row, week in enumerate(weeks):
    for col, day_num in enumerate(week):
        # Do not display any empty cards
        if day_num == 0:
            continue

        cell_left = label_side_gap_frac + col * cell_width_frac
        cell_top = cards_top_y - row * (card_height_frac + row_gap_y_frac)
        cell_bottom = cell_top - card_height_frac

        # Card rectangle
        fig.patches.extend([
            plt.Rectangle(
                (cell_left, cell_bottom),
                cell_width_frac, card_height_frac,
                transform=fig.transFigure, figure=fig,
                color='white', ec='#bbbbbb', lw=1.0, zorder=2
            )
        ])

        # Date number in the top area of the card
        fig.text(
            cell_left + 0.006, cell_top - 0.006,
            str(day_num),
            ha='left', va='top',
            color='#444', fontsize=12, weight='bold', zorder=4
        )

        # List times/tides/phases to the right of the date number (in the top half)
        events = tide_events_by_day.get(day_num, [])
        if events:
            max_lines = 4
            events_to_show = events[:max_lines]

            # Layout within the top area of the card
            pad_top = 0.006
            pad_bottom = 0.004
            top_area_height = max(0.001, line_offset_frac - pad_top - pad_bottom)
            line_step = top_area_height / max(1, len(events_to_show))
            right_pad = 0.006
            text_x = cell_left + cell_width_frac - right_pad

            for idx, (evt_dt, evt_h, evt_phase) in enumerate(events_to_show):
                evt_time = evt_dt.strftime('%H%M')
                # Only show first + second columns: time and height
                evt_txt = f"{evt_time} {evt_h:0.2f}"

                fig.text(
                    text_x,
                    (cell_top - pad_top) - idx * line_step,
                    evt_txt,
                    ha='right', va='top',
                    color='#444', fontsize=8,
                    family='monospace', zorder=4
                )

        # Split line inside the card
        y_line = cell_top - line_offset_frac
        fig.lines.append(
            plt.Line2D(
                [cell_left, cell_left + cell_width_frac],
                [y_line, y_line],
                transform=fig.transFigure,
                color='#bbbbbb', linewidth=1.0, zorder=3
            )
        )

        # Mini-grid axes in the lower half of the card
        grid_top = y_line
        grid_bottom = cell_bottom
        grid_height = max(0.001, grid_top - grid_bottom)
        grid_ax = fig.add_axes([cell_left, grid_bottom, cell_width_frac, grid_height])
        grid_ax.set_zorder(5)
        grid_ax.patch.set_alpha(0)

        grid_ax.set_xlim(0, 24)
        grid_ax.set_ylim(0, 3)
        grid_ax.set_xticks(x_ticks)
        grid_ax.set_yticks(y_ticks)

        # X axis: always show labels on every mini-grid
        grid_ax.set_xticklabels(xticklabels)

        # Y axis: never show the 0 label, and only show labels when there's no card to the left
        is_leftmost_visible = (row_leftmost_col.get(row) == col)
        if is_leftmost_visible:
            grid_ax.set_yticklabels(['', '1', '2', '3'])
        else:
            grid_ax.set_yticklabels([''] * len(yticklabels))

        # Thin light-grey grid lines
        grid_ax.grid(False)
        grid_ax.vlines(x_ticks, ymin=0, ymax=3, colors=grid_color, linewidth=grid_lw, alpha=grid_alpha, zorder=10)
        grid_ax.hlines(y_ticks, xmin=0, xmax=24, colors=grid_color, linewidth=grid_lw, alpha=grid_alpha, zorder=10)

        grid_ax.tick_params(axis='both', which='both', length=0, labelsize=7, pad=1)

        # Clean look
        for spine in grid_ax.spines.values():
            spine.set_visible(False)
        for label in grid_ax.get_yticklabels():
            label.set_horizontalalignment('right')

        # Save mini-grid box for plotting tide curve later
        day_boxes[(year, month, day_num)] = {
            'row': row,
            'col': col,
            'x0': cell_left,
            'x1': cell_left + cell_width_frac,
            'y0': grid_bottom,
            'y1': grid_top,
        }


def draw_tide_curves(fig, year, month, tide_points, day_boxes,
                     y_min=0.0, y_max=3.0,
                     sample_minutes=20,
                     line_color='#808080', line_width=1.0,
                     fill_color=None, fill_alpha=0.25):
    if not tide_points:
        return

    if fill_color is None:
        fill_color = line_color

    # Pick a timezone from the data (fallback to naive)
    tzinfo = tide_points[0][0].tzinfo
    month_start = datetime.datetime(year, month, 1, 0, 0, tzinfo=tzinfo)
    if month == 12:
        month_end = datetime.datetime(year + 1, 1, 1, 0, 0, tzinfo=tzinfo)
    else:
        month_end = datetime.datetime(year, month + 1, 1, 0, 0, tzinfo=tzinfo)

    # Extend a bit for continuity at boundaries
    start = month_start - datetime.timedelta(hours=12)
    end = month_end + datetime.timedelta(hours=12)

    # Pointer for extrema segments
    idx = 0
    n = len(tide_points)

    def height_at(t):
        nonlocal idx
        while idx + 1 < n and tide_points[idx + 1][0] < t:
            idx += 1
        if idx + 1 >= n:
            return None
        t0, y0, _p0 = tide_points[idx]
        t1, y1, _p1 = tide_points[idx + 1]
        if t < t0 or t > t1:
            return None
        return cosine_interp(t, t0, t1, y0, y1)

    step = datetime.timedelta(minutes=sample_minutes)

    # Build sample times including exact day boundaries so the curve/fill
    # reaches the left/right edges of each mini chart.
    times = []
    t = start
    while t <= end:
        times.append(t)
        t += step

    # Add exact day starts/ends for the target month
    for (yy, mm, dd) in {(k[0], k[1], k[2]) for k in day_boxes.keys()}:
        if yy != year or mm != month:
            continue
        day_start = datetime.datetime(year, month, dd, 0, 0, tzinfo=tzinfo)
        day_end = day_start + datetime.timedelta(days=1)
        times.append(day_start)
        times.append(day_end)

    # Ensure month end is included
    times.append(month_end)

    # Sort unique times
    times = sorted(set(times))

    current_x = []
    current_y = []
    current_y0 = []
    prev_pos = None  # (row, col)

    def flush_segment():
        nonlocal current_x, current_y, current_y0
        if len(current_x) >= 2:
            # Fill under curve down to the mini-grid baseline
            if current_y0:
                verts = list(zip(current_x, current_y)) + list(zip(reversed(current_x), list(reversed(current_y0))))
                fig.patches.append(
                    plt.Polygon(
                        verts,
                        closed=True,
                        transform=fig.transFigure,
                        facecolor=fill_color,
                        edgecolor='none',
                        alpha=fill_alpha,
                        zorder=8,
                    )
                )

            # Tide curve line
            fig.add_artist(
                plt.Line2D(
                    current_x, current_y,
                    transform=fig.transFigure,
                    color=line_color,
                    linewidth=line_width,
                    zorder=9,
                )
            )
        current_x = []
        current_y = []
        current_y0 = []

    for t in times:
        h = height_at(t)
        if h is None:
            continue

        # Only plot within the target month
        if t.year != year or t.month != month:
            continue

        key = (year, month, t.day)
        box = day_boxes.get(key)
        if not box:
            continue

        # Break if we jump across rows or non-adjacent columns (hidden blanks)
        pos = (box['row'], box['col'])
        if prev_pos is not None:
            if pos[0] != prev_pos[0] or pos[1] not in (prev_pos[1], prev_pos[1] + 1):
                flush_segment()

        # Map to figure coordinates
        hours = t.hour + (t.minute / 60.0) + (t.second / 3600.0)
        x = box['x0'] + (hours / 24.0) * (box['x1'] - box['x0'])
        hh = min(max(h, y_min), y_max)
        y = box['y0'] + ((hh - y_min) / (y_max - y_min)) * (box['y1'] - box['y0'])

        current_x.append(x)
        current_y.append(y)
        current_y0.append(box['y0'])
        prev_pos = pos

    flush_segment()


# Draw tide curves on top of the mini-grids
draw_tide_curves(fig, year, month, tide_points, day_boxes)

# Save the figure as a .pdf file
fig.savefig('tidal_calendar.pdf', format='pdf')

#plt.show()
