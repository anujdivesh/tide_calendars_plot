from matplotlib import pyplot as plt
import datetime
import calendar
from pathlib import Path
import math
import matplotlib.dates as mdates
import matplotlib as mpl
import textwrap
from astral import LocationInfo
from astral.sun import sun
import requests
import json
import os

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


def get_sun_times_for_month(year, month, location):
    """Generate sunrise/sunset times for all days in a month using astral (returns LOCAL time)."""
    sun_times = {}
    _, num_days = calendar.monthrange(year, month)
    for day in range(1, num_days + 1):
        date = datetime.date(year, month, day)
        try:
            s = sun(location.observer, date=date)
            sunrise_local = s['sunrise'].astimezone(location.tzinfo)
            sunset_local = s['sunset'].astimezone(location.tzinfo)
            sun_times[date] = (sunrise_local.time(), sunset_local.time())
        except Exception:
            sun_times[date] = (None, None)
    return sun_times


def load_moon_icons(icon_dir: Path):
    """Load moon phase icons from the specified directory."""
    moon_icons = {}
    if not icon_dir.exists():
        print(f"Warning: Moon icons directory not found at {icon_dir}")
        return moon_icons

    png_files = list(icon_dir.glob('*.png'))
    print(f"Found {len(png_files)} PNG files in moon_icons directory")

    # Note: "last-quarter" contains "quarter"; match last/first first.
    for png_file in png_files:
        filename = png_file.stem.lower()
        try:
            img = plt.imread(str(png_file))
        except Exception as e:
            print(f"Error loading {png_file}: {e}")
            continue

        if 'last' in filename:
            moon_icons['last_quarter'] = img
        elif 'first' in filename:
            moon_icons['first_quarter'] = img
        elif 'full' in filename:
            moon_icons['full'] = img
        elif 'new' in filename:
            moon_icons['new'] = img

    print(f"Successfully loaded {len(moon_icons)} moon icons")
    return moon_icons


def get_moon_phases_from_usno(year):
    """Fetch major moon phases from USNO API and convert to Fiji time (UTC+12)."""
    url = f"https://aa.usno.navy.mil/api/moon/phases/year?year={year}"
    try:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.exceptions.SSLError:
            print("SSL verification failed. Trying without verification...")
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = requests.get(url, timeout=30, verify=False)
            response.raise_for_status()

        data = response.json()

        phase_mapping = {
            "New Moon": "new",
            "First Quarter": "first_quarter",
            "Full Moon": "full",
            "Last Quarter": "last_quarter",
        }

        UTC_OFFSET = datetime.timedelta(hours=12)
        moon_phases = {}
        for phase_data in data.get('phasedata', []):
            phase_name = phase_data.get('phase')
            if phase_name not in phase_mapping:
                continue

            time_str = phase_data.get('time', '00:00')
            hour = int(time_str[:2])
            minute = int(time_str[3:5])

            phase_time_utc = datetime.datetime(
                phase_data['year'],
                phase_data['month'],
                phase_data['day'],
                hour, minute,
                tzinfo=datetime.timezone.utc,
            )
            phase_time_fiji = phase_time_utc + UTC_OFFSET
            moon_phases[phase_time_fiji.date()] = phase_mapping[phase_name]

        return moon_phases
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching moon phases from USNO: {e}")
        return {}
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing USNO response: {e}")
        return {}


# Define Suva location for sunrise/sunset
SUVA = LocationInfo(
    name="Suva",
    region="Fiji",
    timezone="Pacific/Fiji",
    latitude=-18.1248,
    longitude=178.4501,
)

# --- Output control ---
# When True, renders a single multi-page PDF containing all months of 2026.
RENDER_ALL_MONTHS_2026 = True
ALL_MONTHS_YEAR = 2027
ALL_MONTHS_OUTPUT_PDF = 'tidal_calendar_2027.pdf'

# If running the "all months" mode, generate the combined PDF and exit.
# Uses runpy to re-run this script with different MONTH values while sharing cached data.
if (
    __name__ == "__main__"
    and RENDER_ALL_MONTHS_2026
    and not globals().get("_RUN_AS_CHILD")
):
    from matplotlib.backends.backend_pdf import PdfPages
    import runpy

    moon_icon_dir_env = os.environ.get('MOON_ICON_DIR')
    moon_icon_dir = (
        Path(moon_icon_dir_env).expanduser()
        if moon_icon_dir_env
        else (Path(__file__).parent / 'moon_icons')
    )
    if (not moon_icon_dir.exists()) and (Path(__file__).parent.parent / 'moon_icons').exists():
        moon_icon_dir = Path(__file__).parent.parent / 'moon_icons'

    shared_moon_icons = load_moon_icons(moon_icon_dir)
    shared_all_moon_phases = get_moon_phases_from_usno(ALL_MONTHS_YEAR)

    with PdfPages(ALL_MONTHS_OUTPUT_PDF) as pdf:
        for m in range(1, 13):
            runpy.run_path(
                __file__,
                run_name="__main__",
                init_globals={
                    "YEAR": ALL_MONTHS_YEAR,
                    "MONTH": m,
                    "_RUN_AS_CHILD": True,
                    "_PDF_PAGES": pdf,
                    "_MOON_ICONS": shared_moon_icons,
                    "_ALL_MOON_PHASES": shared_all_moon_phases,
                },
            )
    raise SystemExit

figsize = cm2inch((21,29.7))
fig, ax = plt.subplots(figsize=figsize, dpi=500)
ax.axis('off')

# Draw day cards for the current month, aligned under weekday headings
# Set these to render a specific month (e.g., YEAR=2027, MONTH=1). Leave as None to use current month.
YEAR = globals().get('YEAR', 2027)
MONTH = globals().get('MONTH', 1)

today = datetime.date.today()
year = YEAR if YEAR is not None else today.year
month = MONTH if MONTH is not None else today.month


# Calculate positions in figure coordinates
fig_width_cm, fig_height_cm = 21, 29.7
top_whitespace_cm = 0.0  # full top coverage for header
header_height_cm = 2.2

# Convert cm to figure fraction
top_whitespace_frac = top_whitespace_cm / fig_height_cm
header_height_frac = header_height_cm / fig_height_cm


 # Increase horizontal gaps for more space on left/right
label_side_gap_cm = 2.5  # More space on sides
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
        color='#868686', zorder=1
    )
])

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

# Place weekday labels below the lighter grey area, within 2cm side margins


labels = ["SUNDAY", "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY"]
num_labels = len(labels)
label_y = light_grey_bottom_frac - 0.025  # a little below the light grey area
# Make cards bigger by increasing cell width
cell_width_frac = (label_area_width_frac / num_labels) * 1.15
# Center cards horizontally by shifting the starting point
total_card_width = cell_width_frac * num_labels
side_space = (label_area_width_frac - total_card_width) / 2

# Align header title + month/date text to the chart grid start
chart_left_x = label_side_gap_frac + side_space

fig.text(
    chart_left_x, 1 - top_whitespace_frac - header_height_frac/2 - (0.4 / fig_height_cm),
    'TIDAL PREDICTIONS FOR SUVA',
    ha='left', va='center',
    color='white', fontsize=16, weight='bold', zorder=2
)

fig.text(
    chart_left_x,
    light_grey_bottom_frac + light_grey_height_frac - (0.30 / fig_height_cm),
    month_label + "     Local Standard Time",
    ha='left', va='top',
    color='#111111', fontsize=12, weight='bold', zorder=2
)

for i, label in enumerate(labels):
    # Center label above each table cell
    x = label_side_gap_frac + side_space + (i + 0.5) * cell_width_frac
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
card_height_cm = 3.3

# Vertical gap between week rows (increase to create space above x-axis labels)
row_gap_y_cm = 0.6
row_gap_y_frac = row_gap_y_cm / fig_height_cm

label_table_gap_frac = 0.015
cards_top_y = label_y - label_table_gap_frac

# --- Footer config & reserved space (anchored from bottom of page) ---
# Footer is positioned from the bottom of the page (e.g. 2cm above the bottom edge),
# and the calendar grid reserves space above it to prevent overlap.
FOOTER_BOTTOM_MARGIN_CM = 1.1
FOOTER_GAP_ABOVE_CM = 0.6
FOOTER_ROW_GAP_FRAC = 0.022

# Extra footer notes (bottom-left): add/remove lines here
footer_left_notes = [
    "Height in meters",
    "Prediction datum is Tide Gauge Zero",
]

# Optional icon+text under "Lowest tide of the month" (boolean-controlled)
SHOW_PALOLO_FOOTER = False
PALOLO_FOOTER_DATE = datetime.date(year, 2, 5)
PALOLO_FOOTER_TEXT = "5th February Pololo Rising"
PALOLO_ICON_PATH = Path(__file__).with_name('palolo2.jpg')

# Reserve the Palolo-row spacing even when Palolo is off, so the gap above
# footer_left_notes remains consistent.
RESERVE_PALOLO_FOOTER_SPACE = True

# Estimate how far the footer extends below the top footer row (in cm)
_footer_moon_icon_cm = 0.35
_footer_moon_gap_y_cm = 0.20
_footer_palolo_icon_cm = 0.45
_footer_notes_top_gap_cm = 0.55
_footer_notes_fs = 8

_footer_moon_dir = Path(__file__).parent / 'moon_icons'
if (not _footer_moon_dir.exists()) and (Path(__file__).parent.parent / 'moon_icons').exists():
    _footer_moon_dir = Path(__file__).parent.parent / 'moon_icons'
_footer_moon_paths = sorted(_footer_moon_dir.glob('*.png'))
_n_moon = max(1, len(_footer_moon_paths))

_row_step_cm = _footer_moon_icon_cm + _footer_moon_gap_y_cm
_moon_stack_depth_cm = (_n_moon - 1) * _row_step_cm + (_footer_moon_icon_cm / 2.0)

_footer_row_gap_cm = FOOTER_ROW_GAP_FRAC * fig_height_cm
_palolo_depth_cm = 2.0 * _footer_row_gap_cm + (_footer_palolo_icon_cm / 2.0)
_anchor_depth_cm = max(_moon_stack_depth_cm, _palolo_depth_cm if RESERVE_PALOLO_FOOTER_SPACE else 0.0)

_line_h_cm_notes = (_footer_notes_fs * 1.2 / 72.0) * 2.54
_notes_depth_cm = _anchor_depth_cm + _footer_notes_top_gap_cm + max(1, len(footer_left_notes)) * _line_h_cm_notes

_footer_depth_below_cm = max(_moon_stack_depth_cm, _palolo_depth_cm, _notes_depth_cm) + 0.2
footer_y = (FOOTER_BOTTOM_MARGIN_CM + _footer_depth_below_cm) / fig_height_cm

# Reserve space for the footer + a little gap above it
bottom_margin_frac = min(0.95, footer_y + (FOOTER_GAP_ABOVE_CM / fig_height_cm))
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
y_ticks = [0, 1, 2, 3, 4]
xticklabels = ["12AM", "6AM", "12PM", "6PM", "12AM"]
yticklabels = ["0", "1", "2", "3", "4"]
grid_color = '#d0d0d0'
grid_lw = 0.6
grid_alpha = 1.0

# Tide data file (same folder as this script)
DATA_FILE = 'FJI_242020_Suva_hlw_2026_2027_ltz.csv'
tide_points = load_tide_extrema(Path(__file__).with_name(DATA_FILE))

# Sun times for the month
print(f"Calculating sunrise/sunset times for Suva, {month_label}...")
sun_times = get_sun_times_for_month(year, month, SUVA)
print(f"Generated sun times for {len(sun_times)} days")

# Moon icons + phases (major phases only)
moon_icon_dir_env = os.environ.get('MOON_ICON_DIR')
moon_icon_dir = (
    Path(moon_icon_dir_env).expanduser()
    if moon_icon_dir_env
    else (Path(__file__).parent / 'moon_icons')
)
# Fallback: allow moon_icons/ to live one level above this script (repo root)
if (not moon_icon_dir.exists()) and (Path(__file__).parent.parent / 'moon_icons').exists():
    moon_icon_dir = Path(__file__).parent.parent / 'moon_icons'
print(f"Looking for moon icons in: {moon_icon_dir}")
moon_icons = globals().get('_MOON_ICONS')
if moon_icons is None:
    moon_icons = load_moon_icons(moon_icon_dir)

all_moon_phases = globals().get('_ALL_MOON_PHASES')
if all_moon_phases is None:
    print(f"Fetching moon phase data from USNO for {year}...")
    all_moon_phases = get_moon_phases_from_usno(year)
moon_phases = {d: p for (d, p) in all_moon_phases.items() if d.year == year and d.month == month}

# Optional per-day Palolo icon (palolo2.jpg) shown under the moon icon slot.
# Put `palolo2.jpg` next to this script, then enable + add dates.
SHOW_PALOLO2_IN_CARDS = False
PALOLO2_ICON_PATH = Path(__file__).with_name('palolo2.jpg')
PALOLO2_DATES = set([
    datetime.date(year, month, 5),
])

palolo2_img = None
if SHOW_PALOLO2_IN_CARDS:
    try:
        if not PALOLO2_ICON_PATH.exists():
            print(f"Warning: palolo2 icon not found at {PALOLO2_ICON_PATH}")
        else:
            palolo2_img = plt.imread(str(PALOLO2_ICON_PATH))
    except Exception as e:
        print(f"Warning: failed to load palolo2 icon: {e}")

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

        # Center cards horizontally
        cell_left = label_side_gap_frac + side_space + col * cell_width_frac
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
            cell_left + 0.004, cell_top - 0.006,
            str(day_num),
            ha='left', va='top',
            color='#222', fontsize=10, weight='bold', zorder=3
        )

        # Add moon icon underneath the date (ONLY FOR MAJOR PHASES)
        current_date = datetime.date(year, month, day_num)

        # Icon slot coordinates (used by moon + optional palolo2)
        moon_icon_size_cm = 0.35
        moon_icon_w = moon_icon_size_cm / fig_width_cm
        moon_icon_h = moon_icon_size_cm / fig_height_cm
        icon_left = cell_left + 0.006
        moon_icon_bottom = cell_top - 0.02 - moon_icon_h

        if current_date in moon_phases:
            icon_key = moon_phases[current_date]
            if icon_key in moon_icons:
                icon_ax = fig.add_axes([icon_left, moon_icon_bottom, moon_icon_w, moon_icon_h], zorder=6)
                icon_ax.patch.set_alpha(0)
                icon_ax.imshow(moon_icons[icon_key])
                icon_ax.set_axis_off()

        # Optional palolo2 icon in a small row under the moon icon slot (icon only)
        if (
            SHOW_PALOLO2_IN_CARDS
            and palolo2_img is not None
            and (current_date in PALOLO2_DATES)
        ):
            palolo2_size_cm = 0.30
            palolo2_w = palolo2_size_cm / fig_width_cm
            palolo2_h = palolo2_size_cm / fig_height_cm
            palolo2_gap_cm = 0.06
            palolo2_bottom = moon_icon_bottom - (palolo2_gap_cm / fig_height_cm) - palolo2_h
            palolo2_ax = fig.add_axes([icon_left, palolo2_bottom, palolo2_w, palolo2_h], zorder=6)
            palolo2_ax.patch.set_alpha(0)
            palolo2_ax.imshow(palolo2_img)
            palolo2_ax.set_axis_off()

        # List times/tides/phases to the right of the date number (in the top half)
        events = tide_events_by_day.get(day_num, [])

        # Layout helpers for the top area (used by both tide events and sunrise/sunset line)
        pad_top = 0.004
        font_size = 7
        fig_h_in = fig.get_size_inches()[1]
        fig_w_in = fig.get_size_inches()[0]
        line_step = ((font_size * 1.05) / 72.0) / fig_h_in
        right_pad = 0.004
        text_x = cell_left + cell_width_frac - right_pad
        char_w = ((font_size * 0.60) / 72.0) / fig_w_in
        marker_size = font_size
        marker_color = '#111111'
        marker_edge = 'white'
        marker_edgewidth = 1.0

        if events:
            max_lines = 4
            events_to_show = events[:max_lines]

            # Find monthly max/min tide event for this day
            month_points = [(dt, h) for (dt, h, _p) in tide_points if dt.year == year and dt.month == month]
            max_evt = max(month_points, key=lambda x: x[1]) if month_points else None
            min_evt = min(month_points, key=lambda x: x[1]) if month_points else None

            for idx, (evt_dt, evt_h, evt_phase) in enumerate(events_to_show):
                evt_time = evt_dt.strftime('%I:%M%p').upper()
                evt_txt = f"{evt_time} {evt_h:0.2f}"
                y_pos = (cell_top - pad_top) - idx * line_step

                # Check if this event is the monthly max or min
                is_max = max_evt and abs((evt_dt - max_evt[0]).total_seconds()) < 1 and abs(evt_h - max_evt[1]) < 1e-4
                is_min = min_evt and abs((evt_dt - min_evt[0]).total_seconds()) < 1 and abs(evt_h - min_evt[1]) < 1e-4

                # Plot marker (monthly max/min) right next to the tide time text.
                # Since the tide text is right-aligned, compute the left edge from text length.
                marker_gap_chars = 0.7
                marker_x = text_x - (len(evt_txt) + marker_gap_chars) * char_w
                marker_x = max(cell_left + 0.01, marker_x)
                if is_max or is_min:
                    marker = '^' if is_max else 'v'
                    # Nudge marker slightly downward for better vertical alignment
                    marker_y = y_pos - (0.38 * line_step)
                    fig.add_artist(
                        plt.Line2D(
                            [marker_x], [marker_y],
                            transform=fig.transFigure,
                            linestyle='None',
                            marker=marker,
                            markersize=marker_size,
                            markerfacecolor=marker_color,
                            markeredgecolor=marker_edge,
                            markeredgewidth=marker_edgewidth,
                            zorder=10,
                        )
                    )
                
                fig.text(
                    text_x,
                    y_pos,
                    evt_txt,
                    ha='right', va='top',
                    color='#444', fontsize=font_size,
                    family='monospace', zorder=4
                )

        # Split line inside the card (compute early so we can keep sunrise/sunset above the chart)
        # Move split line lower to create a dedicated row for sunrise/sunset.
        y_line = cell_top - (line_offset_frac * 1.15)
        y_line = max(y_line, cell_bottom + 0.012)

        # Add sunrise/sunset information (EVERY DAY) below tide events
        if current_date in sun_times:
            sunrise_t, sunset_t = sun_times[current_date]

            sun_font_size = 6.5
            sun_bottom_gap = 0.0015
            sun_y_start = y_line + sun_bottom_gap

            sunrise_str = ""
            sunset_str = ""
            if sunrise_t:
                sunrise_str = sunrise_t.strftime('%I:%M%p').upper().lstrip('0')
                if sunrise_str.startswith('0'):
                    sunrise_str = sunrise_str[1:]
            if sunset_t:
                sunset_str = sunset_t.strftime('%I:%M%p').upper().lstrip('0')
                if sunset_str.startswith('0'):
                    sunset_str = sunset_str[1:]

            if sunrise_str and sunset_str:
                # Compact spacing so it stays within the card width
                sun_text = f"↑{sunrise_str} ↓{sunset_str}"
            elif sunrise_str:
                sun_text = f"↑{sunrise_str}"
            elif sunset_str:
                sun_text = f"↓{sunset_str}"
            else:
                sun_text = ""

            if sun_text:
                fig.text(
                    cell_left + cell_width_frac - right_pad,
                    sun_y_start,
                    sun_text,
                    ha='right', va='bottom',
                    color='#444',
                    fontsize=sun_font_size,
                    weight='bold',
                    zorder=4,
                    bbox=dict(boxstyle="round,pad=0.03", facecolor='white', alpha=0.7, edgecolor='none'),
                )

        # Draw the split line
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
            grid_ax.set_yticklabels(['', '1m', '2m', '3m', ''])
        else:
            grid_ax.set_yticklabels([''] * len(yticklabels))

        # Thin light-grey grid lines
        grid_ax.grid(False)
        grid_ax.vlines(x_ticks, ymin=0, ymax=4, colors=grid_color, linewidth=grid_lw, alpha=grid_alpha, zorder=10)
        grid_ax.hlines(y_ticks, xmin=0, xmax=24, colors=grid_color, linewidth=grid_lw, alpha=grid_alpha, zorder=10)

        # Add a little extra space between the chart and the bottom time labels
        grid_ax.tick_params(axis='x', which='both', length=0, labelsize=6, pad=3)
        grid_ax.tick_params(axis='y', which='both', length=0, labelsize=6, pad=1)

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

    def append_point(box, hours, height):
        nonlocal current_x, current_y, current_y0, prev_pos
        x = box['x0'] + (hours / 24.0) * (box['x1'] - box['x0'])
        hh = min(max(height, y_min), y_max)
        y = box['y0'] + ((hh - y_min) / (y_max - y_min)) * (box['y1'] - box['y0'])
        current_x.append(x)
        current_y.append(y)
        current_y0.append(box['y0'])
        prev_pos = (box['row'], box['col'])

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

        is_midnight = (t.hour == 0 and t.minute == 0 and t.second == 0 and t.microsecond == 0)

        # Add a synthetic endpoint at x=24 for the *previous* day at midnight boundaries.
        # This guarantees the curve/fill touches the right edge of each mini chart.
        if is_midnight and prev_pos is not None:
            prev_day = t - datetime.timedelta(days=1)
            if prev_day.year == year and prev_day.month == month:
                prev_box = day_boxes.get((year, month, prev_day.day))
                if prev_box and (prev_box['row'], prev_box['col']) == prev_pos:
                    append_point(prev_box, 24.0, h)

        # Only plot points that belong to the target month/day boxes
        if t.year != year or t.month != month:
            continue

        box = day_boxes.get((year, month, t.day))
        if not box:
            continue

        # Break if we jump across rows or non-adjacent columns (hidden blanks)
        pos = (box['row'], box['col'])
        if prev_pos is not None:
            if pos[0] != prev_pos[0] or pos[1] not in (prev_pos[1], prev_pos[1] + 1):
                flush_segment()

        hours = t.hour + (t.minute / 60.0) + (t.second / 3600.0)
        append_point(box, hours, h)

    flush_segment()


def mark_month_max_tide(fig, year, month, tide_points, day_boxes,
                        y_min=0.0, y_max=3.0,
                        marker_color='#111111', marker_size=8, border_color='white', border_width=1.0):
    """Mark the highest tide of the month with an upward triangle."""
    month_points = [(dt, h) for (dt, h, _p) in tide_points if dt.year == year and dt.month == month]
    if not month_points:
        return

    max_dt, max_h = max(month_points, key=lambda x: x[1])
    box = day_boxes.get((year, month, max_dt.day))
    if not box:
        return

    hours = max_dt.hour + (max_dt.minute / 60.0) + (max_dt.second / 3600.0)
    x = box['x0'] + (hours / 24.0) * (box['x1'] - box['x0'])
    hh = min(max(max_h, y_min), y_max)
    y = box['y0'] + ((hh - y_min) / (y_max - y_min)) * (box['y1'] - box['y0'])

    # Nudge marker above the curve (convert points -> figure fraction)
    fig_h_in = fig.get_size_inches()[1]
    # For an upward triangle marker, a ~0.45*markersize offset usually places
    # the bottom point of the marker right on the curve.
    dy = ((marker_size * 0.45) / 72.0) / fig_h_in
    y = min(y + dy, box['y1'] - (0.5 / 72.0) / fig_h_in)

    fig.add_artist(
        plt.Line2D(
            [x], [y],
            transform=fig.transFigure,
            linestyle='None',
            marker='^',
            markersize=marker_size,
            markerfacecolor=marker_color,
            markeredgecolor=border_color,
            markeredgewidth=border_width,
            zorder=12,
        )
    )


def mark_month_min_tide(fig, year, month, tide_points, day_boxes,
                        y_min=0.0, y_max=3.0,
                        marker_color='#111111', marker_size=8, border_color='white', border_width=1.0):
    """Mark the lowest tide of the month with a downward triangle."""
    month_points = [(dt, h) for (dt, h, _p) in tide_points if dt.year == year and dt.month == month]
    if not month_points:
        return

    min_dt, min_h = min(month_points, key=lambda x: x[1])
    box = day_boxes.get((year, month, min_dt.day))
    if not box:
        return

    hours = min_dt.hour + (min_dt.minute / 60.0) + (min_dt.second / 3600.0)
    x = box['x0'] + (hours / 24.0) * (box['x1'] - box['x0'])
    hh = min(max(min_h, y_min), y_max)
    y = box['y0'] + ((hh - y_min) / (y_max - y_min)) * (box['y1'] - box['y0'])

    # Nudge marker below the curve so the top point touches the curve.
    fig_h_in = fig.get_size_inches()[1]
    dy = ((marker_size * 0.45) / 72.0) / fig_h_in
    y = max(y - dy, box['y0'] + (0.5 / 72.0) / fig_h_in)

    fig.add_artist(
        plt.Line2D(
            [x], [y],
            transform=fig.transFigure,
            linestyle='None',
            marker='v',
            markersize=marker_size,
            markerfacecolor=marker_color,
            markeredgecolor=border_color,
            markeredgewidth=border_width,
            zorder=12,
        )
    )


# Draw tide curves on top of the mini-grids
draw_tide_curves(fig, year, month, tide_points, day_boxes)

# Mark the highest tide of the month
mark_month_max_tide(fig, year, month, tide_points, day_boxes)

# Mark the lowest tide of the month
mark_month_min_tide(fig, year, month, tide_points, day_boxes)


# --- Footer notes ---
# `footer_y` is computed earlier from the page bottom margin.
footer_y = max(footer_y, 0.01)  # Clamp to stay on page

# Downward triangle (lowest tide) y-position and row spacing
footer_low_y = footer_y - (FOOTER_ROW_GAP_FRAC)
footer_row_gap = footer_y - footer_low_y

# Draw upward triangle icon and label (match plot marker size)
footer_marker_size = 8  # matches mark_month_max_tide/mark_month_min_tide default marker_size
footer_marker_color = '#111111'
footer_marker_edge = 'white'
footer_marker_edgewidth = 1.0
footer_text = "Highest tide of the month"

# Palolo footer geometry (also used as a *virtual* anchor for footer_left_notes)
palolo_icon_cm = 0.45
palolo_icon_w_default = palolo_icon_cm / fig_width_cm
palolo_icon_h_default = palolo_icon_cm / fig_height_cm
palolo_center_y_target_default = footer_low_y - footer_row_gap
palolo_bottom_min = 0.012
virtual_palolo_bottom = max(palolo_bottom_min, palolo_center_y_target_default - (palolo_icon_h_default / 2))

palolo_bottom = None
palolo_center_y = None
palolo_icon_h = None
palolo_icon_w = None
if SHOW_PALOLO_FOOTER and (month == PALOLO_FOOTER_DATE.month):
    palolo_icon_w = palolo_icon_w_default
    palolo_icon_h = palolo_icon_h_default
    palolo_bottom = virtual_palolo_bottom
    palolo_center_y = palolo_bottom + (palolo_icon_h / 2)

# Align footer content with the left edge of the card grid
footer_left_x = label_side_gap_frac + side_space
footer_marker_x = footer_left_x + 0.003
footer_text_x = footer_left_x + 0.013

# Triangle marker (always use Line2D for figure coords)
fig.add_artist(
    plt.Line2D(
        [footer_marker_x], [footer_y],
        transform=fig.transFigure,
        linestyle='None',
        marker='^',
        markersize=footer_marker_size,
        markerfacecolor=footer_marker_color,
        markeredgecolor=footer_marker_edge,
        markeredgewidth=footer_marker_edgewidth,
        zorder=20,
    )
)

# Text label, left-aligned with cards, a bit right of the marker
footer_high_text = fig.text(
    footer_text_x, footer_y,
    footer_text,
    ha='left', va='center',
    color='#222', fontsize=9, zorder=20
)

# Moon icons + labels: 1cm to the right of the footer_high_text, stacked vertically
try:
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bbox = footer_high_text.get_window_extent(renderer=renderer)
    (text_right_x, _text_top_y) = fig.transFigure.inverted().transform((bbox.x1, bbox.y1))

    # Keep footer content within 1cm of the page right edge
    page_right_limit_x = 1.0 - (1.0 / fig_width_cm)
    right_margin = 0.002
    content_right_limit_x = min(page_right_limit_x, 1.0 - right_margin)

    moon_x = text_right_x + (1.0 / fig_width_cm)  # 1cm spacing to the right
    icon_cm = 0.35
    icon_gap_y_cm = 0.20
    icon_w = icon_cm / fig_width_cm
    icon_h = icon_cm / fig_height_cm
    moon_x = min(moon_x, content_right_limit_x - icon_w)

    moon_dir = Path(__file__).parent / 'moon_icons'
    if (not moon_dir.exists()) and (Path(__file__).parent.parent / 'moon_icons').exists():
        moon_dir = Path(__file__).parent.parent / 'moon_icons'
    moon_paths = sorted(moon_dir.glob('*.png'))
    moon_labels = [
        'First quarter',
        'Full Moon',
        'Last quarter',
        'New Moon',
    ]

    moon_label_artists = []
    moon_right_x = moon_x + icon_w

    for i, icon_path in enumerate(moon_paths):
        yy = footer_y - i * ((icon_cm + icon_gap_y_cm) / fig_height_cm)
        icon_bottom = yy - icon_h / 2

        icon_ax = fig.add_axes([moon_x, icon_bottom, icon_w, icon_h], zorder=21)
        icon_ax.patch.set_alpha(0)
        icon_ax.imshow(plt.imread(str(icon_path)))
        icon_ax.set_axis_off()

        label_x = moon_x + icon_w + (0.18 / fig_width_cm)
        label_txt = moon_labels[i % len(moon_labels)]
        moon_label = fig.text(
            label_x, yy,
            label_txt,
            ha='left', va='center',
            color='#222', fontsize=9, zorder=21
        )
        moon_label_artists.append(moon_label)

    # Bottom-left notes: anchor from the bottom of the page
    # Requirement: the notes block sits 2cm above the page bottom.
    if footer_left_notes:
        fs_notes = 8
        fig_h_in_notes = fig.get_size_inches()[1]
        line_h_notes = ((fs_notes * 1.2) / 72.0) / fig_h_in_notes

        notes_bottom_y = (FOOTER_BOTTOM_MARGIN_CM / fig_height_cm)
        n_lines = len(footer_left_notes)

        for i, line in enumerate(footer_left_notes):
            # Place lines upward so the bottom of the last line is exactly at notes_bottom_y.
            y = notes_bottom_y + (n_lines - 1 - i) * line_h_notes
            fig.text(
                footer_text_x,
                max(0.01, y),
                line,
                ha='left', va='bottom',
                color='#222', fontsize=fs_notes, zorder=21,
            )

    # Place copyright + disclaimer block 3cm to the right of the moon column
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for t in moon_label_artists:
        bb = t.get_window_extent(renderer=renderer)
        (x1, _y1) = fig.transFigure.inverted().transform((bb.x1, bb.y1))
        moon_right_x = max(moon_right_x, x1)

    # Sunrise/Sunset legend column: stacked like moon, to the right of moon column
    sun_x = moon_right_x + (1.0 / fig_width_cm)

    # Measure max label width so we can clamp inside the page
    fs_sun = 9
    tmp_sunrise = fig.text(0, 0, 'Sunrise', fontsize=fs_sun, alpha=0, transform=fig.transFigure)
    tmp_sunset = fig.text(0, 0, 'Sunset', fontsize=fs_sun, alpha=0, transform=fig.transFigure)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    sunrise_w = tmp_sunrise.get_window_extent(renderer=renderer).width / fig.bbox.width
    sunset_w = tmp_sunset.get_window_extent(renderer=renderer).width / fig.bbox.width
    tmp_sunrise.remove()
    tmp_sunset.remove()

    # Horizontal gap between the arrow glyph and the label text
    sun_marker_gap = (0.28 / fig_width_cm)
    sun_col_w = sun_marker_gap + max(sunrise_w, sunset_w)
    sun_x = min(sun_x, content_right_limit_x - sun_col_w)

    sun_label_artists = []
    sun_right_x = sun_x
    sun_rows = [
        ('Sunrise', '↑', '#000000', footer_y),
        ('Sunset', '↓', '#000000', footer_y - ((icon_cm + icon_gap_y_cm) / fig_height_cm)),
    ]

    for label_txt, arrow_txt, color_txt, yy in sun_rows:
        # Use normal text glyphs for thinner, non-bold arrows (avoid mathtext '$↑$')
        fig.text(
            sun_x, yy,
            arrow_txt,
            ha='left', va='center',
            color=color_txt, fontsize=10, weight='bold', zorder=21,
        )
        sun_label = fig.text(
            sun_x + sun_marker_gap, yy,
            label_txt,
            ha='left', va='center',
            color='#222', fontsize=9, zorder=21
        )
        sun_label_artists.append(sun_label)

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for t in sun_label_artists:
        bb = t.get_window_extent(renderer=renderer)
        (x1, _y1) = fig.transFigure.inverted().transform((bb.x1, bb.y1))
        sun_right_x = max(sun_right_x, x1)

    # Place copyright/disclaimer block just to the right of the moon/sun legend columns
    # (smaller gap to reduce whitespace and shift the block left)
    right_block_gap_cm = 0.8
    right_block_x = max(moon_right_x, sun_right_x) + (right_block_gap_cm / fig_width_cm)
    right_block_x = min(right_block_x, content_right_limit_x)

    copyright_label = "© Copyright"
    copyright_value = "2026, Pacific Community SPC"
    disclaimer_label = "Disclaimer"
    disclaimer_value = (
        "These tide predictions are supplied in good faith and are belived to be correct. "
        "They are not necessarily related to a local hydrographic chart datum. "
        "\n"
        "\n"
        "No warranty is given in respect to errors, omissions, or suitability for any purpose."
    )

    fs = 8
    fig_h_in = fig.get_size_inches()[1]
    line_h = ((fs * 1.2) / 72.0) / fig_h_in

    # Compute a colon x-position so both ':' align vertically
    tmp1 = fig.text(0, 0, copyright_label, fontsize=fs, alpha=0,weight='bold', transform=fig.transFigure)
    tmp2 = fig.text(0, 0, disclaimer_label, fontsize=fs, alpha=0,weight='bold', transform=fig.transFigure)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    w1 = tmp1.get_window_extent(renderer=renderer).width / fig.bbox.width
    w2 = tmp2.get_window_extent(renderer=renderer).width / fig.bbox.width
    tmp1.remove()
    tmp2.remove()

    colon_gap = (0.12 / fig_width_cm)
    value_gap = (0.18 / fig_width_cm)
    colon_x = right_block_x + max(w1, w2) + colon_gap
    max_x = content_right_limit_x
    colon_x = min(colon_x, max_x - 0.01)
    value_x = min(colon_x + value_gap, max_x - 0.01)

    # Copyright line (inline with Highest tide footer)
    fig.text(
        colon_x - colon_gap, footer_y,
        copyright_label,
        ha='right', va='center',
        color='#222', fontsize=fs, zorder=21, weight='bold'
    )
    fig.text(
        colon_x, footer_y,
        ":",
        ha='center', va='center',
        color='#222', fontsize=fs, zorder=21
    )
    fig.text(
        value_x, footer_y,
        copyright_value,
        ha='left', va='center',
        color='#222', fontsize=fs, zorder=21
    )

    # Disclaimer line below
    disc_y = footer_y - (0.75 * line_h)
    fig.text(
        colon_x - colon_gap, disc_y,
        disclaimer_label,
        ha='right', va='top',
        color='#222', fontsize=fs, zorder=21, weight='bold'
    )
    fig.text(
        colon_x, disc_y,
        ":",
        ha='center', va='top',
        color='#222', fontsize=fs, zorder=21
    )

    # Wrap disclaimer based on the *actual* available pixel width, preserving manual line breaks
    avail_w = max(0.10, max_x - value_x)
    avail_px = avail_w * fig.bbox.width
    probe = fig.text(0, 0, "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz", fontsize=fs, alpha=0, transform=fig.transFigure)
    fig.canvas.draw()
    probe_w_px = probe.get_window_extent(renderer=renderer).width
    probe.remove()
    avg_char_px = max(5.0, probe_w_px / 52.0)
    # Allow more words per line in the disclaimer by increasing wrap_chars by 20%
    wrap_chars = max(35, int(avail_px / avg_char_px * 1.2))
    # Split disclaimer on manual line breaks, wrap each line, then join
    disclaimer_lines = disclaimer_value.split('\n')
    disclaimer_wrapped = '\n'.join(textwrap.fill(line, width=wrap_chars) for line in disclaimer_lines)
    fig.text(
        value_x, disc_y,
        disclaimer_wrapped,
        ha='left', va='top',
        color='#222', fontsize=fs, zorder=21,
        linespacing=1.15,
    )
except Exception:
    pass

# Downward triangle and text for lowest tide
fig.add_artist(
    plt.Line2D(
        [footer_marker_x], [footer_low_y],
        transform=fig.transFigure,
        linestyle='None',
        marker='v',
        markersize=footer_marker_size,
        markerfacecolor=footer_marker_color,
        markeredgecolor=footer_marker_edge,
        markeredgewidth=footer_marker_edgewidth,
        zorder=20,
    )
)
fig.text(
    footer_text_x, footer_low_y,
    "Lowest tide of the month",
    ha='left', va='center',
    color='#222', fontsize=9, zorder=20
)

# Optional Palolo entry under the lowest-tide legend
if SHOW_PALOLO_FOOTER and (month == PALOLO_FOOTER_DATE.month):
    try:
        if not PALOLO_ICON_PATH.exists():
            print(f"Warning: palolo icon not found at {PALOLO_ICON_PATH}")
        palolo_img = plt.imread(str(PALOLO_ICON_PATH))

        # (palolo_icon_w/palolo_icon_h/palolo_bottom/palolo_center_y already computed above)
        if palolo_icon_w is None or palolo_icon_h is None or palolo_bottom is None or palolo_center_y is None:
            palolo_icon_cm = 0.45
            palolo_icon_w = palolo_icon_cm / fig_width_cm
            palolo_icon_h = palolo_icon_cm / fig_height_cm
            palolo_center_y_target = footer_low_y - footer_row_gap
            palolo_bottom_min = 0.012
            palolo_bottom = max(palolo_bottom_min, palolo_center_y_target - (palolo_icon_h / 2))
            palolo_center_y = palolo_bottom + (palolo_icon_h / 2)

        # Center the icon on the same x as the triangle markers
        palolo_left = max(0.0, footer_marker_x - (palolo_icon_w / 2))

        palolo_ax = fig.add_axes(
            [palolo_left, palolo_bottom, palolo_icon_w, palolo_icon_h],
            zorder=21,
        )
        palolo_ax.patch.set_alpha(0)
        palolo_ax.imshow(palolo_img)
        palolo_ax.set_axis_off()

        fig.text(
            footer_text_x,
            palolo_center_y,
            PALOLO_FOOTER_TEXT,
            ha='left', va='center',
            color='#222', fontsize=8, zorder=21,
        )
    except Exception as e:
        print(f"Warning: failed to render palolo footer entry: {e}")
elif SHOW_PALOLO_FOOTER and (month != PALOLO_FOOTER_DATE.month):
    print(
        f"Note: SHOW_PALOLO_FOOTER is True, but calendar month={month} doesn't match PALOLO_FOOTER_DATE.month={PALOLO_FOOTER_DATE.month}"
    )

# Save the figure as a .pdf file (single-page) or append to a multi-page PDF
_pdf_pages = globals().get('_PDF_PAGES')
if _pdf_pages is not None:
    _pdf_pages.savefig(fig)
else:
    fig.savefig('tidal_calendar.pdf', format='pdf')

plt.close(fig)

#plt.show()
