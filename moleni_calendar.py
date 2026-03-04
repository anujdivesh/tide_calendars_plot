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
 
 
def get_sun_times_for_month(year, month, location):
    """Generate sunrise/sunset times for all days in a month using astral (returns LOCAL time)"""
    sun_times = {}
    _, num_days = calendar.monthrange(year, month)
   
    for day in range(1, num_days + 1):
        date = datetime.date(year, month, day)
        try:
            s = sun(location.observer, date=date)
            # Get the times in the location's local timezone (Pacific/Fiji)
            sunrise_local = s['sunrise'].astimezone(location.tzinfo)
            sunset_local = s['sunset'].astimezone(location.tzinfo)
           
            # Store just the time components (without timezone info for display)
            sun_times[date] = (sunrise_local.time(), sunset_local.time())
           
        except Exception as e:
            print(f"Could not calculate sun times for {date}: {e}")
            sun_times[date] = (None, None)
   
    return sun_times
 
def load_moon_icons(icon_dir):
    """Load moon phase icons from the specified directory"""
    moon_icons = {}
   
    if not icon_dir.exists():
        print(f"Warning: Moon icons directory not found at {icon_dir}")
        return moon_icons
   
    # Look for PNG files in the directory
    png_files = list(icon_dir.glob('*.png'))
    print(f"Found {len(png_files)} PNG files in moon_icons directory")
   
    # Map filenames to phase types (based on your file names)
    # Note: be careful with substring matching: "last-quarter" contains "quarter".
    for png_file in png_files:
        filename = png_file.stem.lower()  # filename without extension

        try:
            img = plt.imread(str(png_file))
        except Exception as e:
            print(f"Error loading {png_file}: {e}")
            continue

        if 'last' in filename:
            moon_icons['last_quarter'] = img
            print(f"✅ Loaded Last Quarter moon icon from {png_file.name}")
        elif 'first' in filename:
            moon_icons['first_quarter'] = img
            print(f"✅ Loaded First Quarter moon icon from {png_file.name}")
        elif 'full' in filename:
            moon_icons['full'] = img
            print(f"✅ Loaded Full Moon icon from {png_file.name}")
        elif 'new' in filename:
            moon_icons['new'] = img
            print(f"✅ Loaded New Moon icon from {png_file.name}")
        else:
            print(f"Skipping unrecognized moon icon filename: {png_file.name}")
   
    print(f"Successfully loaded {len(moon_icons)} moon icons")
    return moon_icons
 
 
def get_moon_phases_from_usno(year):
    """Fetch moon phase data from USNO API for the entire year and convert to Fiji time"""
    url = f"https://aa.usno.navy.mil/api/moon/phases/year?year={year}"
   
    try:
        print(f"Fetching moon phase data from USNO for {year}...")
       
        # Try with SSL verification first
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
        except requests.exceptions.SSLError:
            # If SSL fails, try without verification (less secure but works)
            print("SSL verification failed. Trying without verification...")
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            response = requests.get(url, timeout=30, verify=False)
            response.raise_for_status()
       
        data = response.json()
       
        # Create dictionary mapping dates to phases (icons only, no times)
        moon_phases = {}  # For icons (date -> phase)
       
        phase_mapping = {
            "New Moon": "new",
            "First Quarter": "first_quarter",
            "Full Moon": "full",
            "Last Quarter": "last_quarter"
        }
       
        # Fiji is UTC+12
        UTC_OFFSET = datetime.timedelta(hours=12)
       
        for phase_data in data.get('phasedata', []):
            # Parse the UTC time from the API
            hour = int(phase_data['time'][:2])
            minute = int(phase_data['time'][3:5])
           
            phase_time_utc = datetime.datetime(
                phase_data['year'],
                phase_data['month'],
                phase_data['day'],
                hour, minute,
                tzinfo=datetime.timezone.utc
            )
           
            # Convert to Fiji time (UTC+12)
            phase_time_fiji = phase_time_utc + UTC_OFFSET
           
            # Get the date in Fiji time (might be different day if time crosses midnight)
            fiji_date = phase_time_fiji.date()
           
            phase_name = phase_data['phase']
            if phase_name in phase_mapping:
                # Store for icon placement (use Fiji date)
                moon_phases[fiji_date] = phase_mapping[phase_name]
               
                # Print with Fiji time (for console output only)
                time_str = phase_time_fiji.strftime('%I:%M%p').upper().lstrip('0')
                if time_str.startswith('0'):
                    time_str = time_str[1:]
                print(f"  Found {phase_name} on {fiji_date} at {time_str} Fiji Time (UTC: {phase_data['time']})")
       
        print(f"\n✅ Successfully loaded {len(moon_phases)} moon phases from USNO")
        return moon_phases  # Now only returns one dictionary
       
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching data from USNO: {e}")
        return {}
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing USNO response: {e}")
        return {}
 
 
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
 
# Define Suva location
SUVA = LocationInfo(
    name="Suva",
    region="Fiji",
    timezone="Pacific/Fiji",
    latitude=-18.1248,
    longitude=178.4501
)
 
figsize = cm2inch((21,29.7))
fig, ax = plt.subplots(figsize=figsize, dpi=1000)
ax.axis('off')
 
# Draw day cards for the current month, aligned under weekday headings
# Set these to render a specific month (e.g., YEAR=2025, MONTH=2). Leave as None to use current month.
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
# Make cards bigger by increasing cell width
cell_width_frac = (label_area_width_frac / num_labels) * 1.15
# Center cards horizontally by shifting the starting point
total_card_width = cell_width_frac * num_labels
side_space = (label_area_width_frac - total_card_width) / 2
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
 
# Card geometry - Adjusted for better space utilization
card_height_cm = 4.5  # Increased slightly to accommodate both tide events and sun info
 
# Vertical gap between week rows
row_gap_y_cm = 0.6
row_gap_y_frac = row_gap_y_cm / fig_height_cm
 
label_table_gap_frac = 0.015
cards_top_y = label_y - label_table_gap_frac
bottom_margin_frac = 0.08
available_height_frac = cards_top_y - bottom_margin_frac
 
max_card_height_frac = (available_height_frac - (num_rows - 1) * row_gap_y_frac) / max(1, num_rows)
card_height_frac = min(card_height_cm / fig_height_cm, max_card_height_frac)
 
# Split line inside the card - moved lower to create more space for text
line_offset_cm_target = 2.4  # Increased to leave more room for text above
card_height_cm_effective = card_height_frac * fig_height_cm
line_offset_cm = min(line_offset_cm_target, card_height_cm_effective * 0.6)
line_offset_frac = line_offset_cm / fig_height_cm
 
# Mini-grid style
x_ticks = [0, 6, 12, 18, 24]
y_ticks = [0, 1, 2, 3, 4]
xticklabels = ["0", "6", "12", "18", "0"]
yticklabels = ["0", "1", "2", "3", "4"]
grid_color = '#d0d0d0'
grid_lw = 0.6
grid_alpha = 1.0
 
# Tide data file (same folder as this script)
DATA_FILE = '66840_hlw.data'
tide_points = load_tide_extrema(Path(__file__).with_name(DATA_FILE))
 
# Generate sun times for the month using astral (EVERY DAY)
print(f"Calculating sunrise/sunset times for Suva, {month_label}...")
sun_times = get_sun_times_for_month(year, month, SUVA)
print(f"Generated sun times for {len(sun_times)} days")
 
# Load moon icons (default to ./moon_icons next to this script; allow override via MOON_ICON_DIR)
moon_icon_dir_env = os.environ.get('MOON_ICON_DIR')
moon_icon_dir = (
    Path(moon_icon_dir_env).expanduser()
    if moon_icon_dir_env
    else (Path(__file__).parent / 'moon_icons')
)
print(f"Looking for moon icons in: {moon_icon_dir}")
moon_icons = load_moon_icons(moon_icon_dir)
 
# Get moon phases from USNO API for the entire year (with Fiji time conversion)
print(f"\nFetching moon phase data from USNO for {year}...")
all_moon_phases = get_moon_phases_from_usno(year)
 
# Filter moon phases for the current month
moon_phases = {}
for date, phase in all_moon_phases.items():
    if date.year == year and date.month == month:
        moon_phases[date] = phase
 
print(f"\nMoon phases for {month_label}:")
for date, phase in sorted(moon_phases.items()):
    print(f"  {date}: {phase}")
 
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
        if current_date in moon_phases:
            icon_key = moon_phases[current_date]
            if icon_key in moon_icons:
                # Create a small axes for the moon icon
                icon_size_cm = 0.35
                icon_width_frac = icon_size_cm / fig_width_cm
                icon_height_frac = icon_size_cm / fig_height_cm
               
                # Position icon below the date (no time displayed underneath)
                icon_left = cell_left + 0.006
                icon_bottom = cell_top - 0.02 - icon_height_frac
               
                icon_ax = fig.add_axes([icon_left, icon_bottom, icon_width_frac, icon_height_frac], zorder=6)
                icon_ax.patch.set_alpha(0)
                icon_ax.imshow(moon_icons[icon_key])
                icon_ax.set_axis_off()
               
                print(f"✅ Added moon icon for {current_date}: {icon_key}")
            else:
                print(f"⚠️ Moon phase {icon_key} found but icon not loaded")
 
        # List times/tides/phases to the right of the date number
        events = tide_events_by_day.get(day_num, [])
       
        # Layout within the top area of the card
        pad_top = 0.002
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
 
        # Position for tide events (right-aligned at top)
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
 
                # Plot marker (monthly max/min)
                marker_gap_chars = 0.7
                marker_x = text_x - (len(evt_txt) + marker_gap_chars) * char_w
                marker_x = max(cell_left + 0.01, marker_x)
                if is_max or is_min:
                    marker = '^' if is_max else 'v'
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
 
        # Add sunrise/sunset information - IN ONE ROW WITH ARROWS (EVERY DAY)
        if current_date in sun_times:
            sunrise, sunset = sun_times[current_date]
           
            # Position for sun info (below tide events, left-aligned)
            sun_font_size = 6
            sun_line_step = ((sun_font_size * 1.2) / 72.0) / fig_h_in
           
            # ALWAYS position sun info as if there were 4 tide events for consistency
            sun_y_start = (cell_top - pad_top) - (4 * line_step) - (sun_line_step * 0.5)
           
            # Format times
            sunrise_str = ""
            sunset_str = ""
           
            if sunrise:
                sunrise_str = sunrise.strftime('%I:%M%p').upper().lstrip('0')
                if sunrise_str.startswith('0'):
                    sunrise_str = sunrise_str[1:]
           
            if sunset:
                sunset_str = sunset.strftime('%I:%M%p').upper().lstrip('0')
                if sunset_str.startswith('0'):
                    sunset_str = sunset_str[1:]
           
            # Create combined sun string with arrows (EVERY DAY)
            if sunrise_str and sunset_str:
                sun_text = f"↑ {sunrise_str}   ↓ {sunset_str}"
            elif sunrise_str:
                sun_text = f"↑ {sunrise_str}"
            elif sunset_str:
                sun_text = f"↓ {sunset_str}"
            else:
                sun_text = ""
           
            if sun_text:
                fig.text(
                    cell_left + 0.002,
                    sun_y_start,
                    sun_text,
                    ha='left', va='top',
                    color='#444',
                    fontsize=sun_font_size,
                    weight='bold',
                    zorder=4,
                    bbox=dict(boxstyle="round,pad=0.1", facecolor='white', alpha=0.7, edgecolor='none')
                )
 
        # Split line inside the card
        y_line = cell_top - (line_offset_frac * 0.65)
        fig.lines.append(
            plt.Line2D(
                [cell_left, cell_left + cell_width_frac],
                [y_line, y_line],
                transform=fig.transFigure,
                color='#bbbbbb', linewidth=1.0, zorder=3
            )
        )
 
        # Mini-grid axes (tide sine plot) — make chart area a bit shorter
        # Keep the TOP aligned with the split line; add extra bottom margin by shrinking height.
        grid_top = y_line
        full_h = max(0.001, grid_top - cell_bottom)
        mini_grid_height_scale = 0.86
        grid_height = max(0.001, full_h * mini_grid_height_scale)
        grid_bottom = grid_top - grid_height

        grid_ax = fig.add_axes([cell_left, grid_bottom, cell_width_frac, grid_height])
        grid_ax.set_zorder(5)
        grid_ax.patch.set_alpha(0)
 
        grid_ax.set_xlim(0, 24)
        grid_ax.set_ylim(0, 4)
        grid_ax.set_xticks(x_ticks)
        grid_ax.set_yticks(y_ticks)
        grid_ax.set_xticklabels(xticklabels)
 
        is_leftmost_visible = (row_leftmost_col.get(row) == col)
        if is_leftmost_visible:
            grid_ax.set_yticklabels(['', '1m', '2m', '3m', ''])
        else:
            grid_ax.set_yticklabels([''] * len(yticklabels))
 
        grid_ax.grid(False)
        grid_ax.vlines(x_ticks, ymin=0, ymax=4, colors=grid_color, linewidth=grid_lw, alpha=grid_alpha, zorder=10)
        grid_ax.hlines(y_ticks, xmin=0, xmax=24, colors=grid_color, linewidth=grid_lw, alpha=grid_alpha, zorder=10)
 
        grid_ax.tick_params(axis='both', which='both', length=0, labelsize=7, pad=2)
 
        for spine in grid_ax.spines.values():
            spine.set_visible(False)
        for label in grid_ax.get_yticklabels():
            label.set_horizontalalignment('right')
 
        day_boxes[(year, month, day_num)] = {
            'row': row,
            'col': col,
            'x0': cell_left,
            'x1': cell_left + cell_width_frac,
            'y0': grid_bottom,
            'y1': grid_top,
        }
 
 
def draw_tide_curves(fig, year, month, tide_points, day_boxes,
                     y_min=0.0, y_max=4.0,
                     sample_minutes=20,
                     line_color='#808080', line_width=1.0,
                     fill_color=None, fill_alpha=0.25):
    if not tide_points:
        return
 
    if fill_color is None:
        fill_color = line_color
 
    tzinfo = tide_points[0][0].tzinfo
    month_start = datetime.datetime(year, month, 1, 0, 0, tzinfo=tzinfo)
    if month == 12:
        month_end = datetime.datetime(year + 1, 1, 1, 0, 0, tzinfo=tzinfo)
    else:
        month_end = datetime.datetime(year, month + 1, 1, 0, 0, tzinfo=tzinfo)
 
    start = month_start - datetime.timedelta(hours=12)
    end = month_end + datetime.timedelta(hours=12)
 
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
 
    times = []
    t = start
    while t <= end:
        times.append(t)
        t += step
 
    for (yy, mm, dd) in {(k[0], k[1], k[2]) for k in day_boxes.keys()}:
        if yy != year or mm != month:
            continue
        day_start = datetime.datetime(year, month, dd, 0, 0, tzinfo=tzinfo)
        day_end = day_start + datetime.timedelta(days=1)
        times.append(day_start)
        times.append(day_end)
 
    times.append(month_end)
    times = sorted(set(times))
 
    current_x = []
    current_y = []
    current_y0 = []
    prev_pos = None
 
    def flush_segment():
        nonlocal current_x, current_y, current_y0
        if len(current_x) >= 2:
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
 
    y_inset_frac = 0.06  # shrink curve slightly within the grid box

    for t in times:
        h = height_at(t)
        if h is None:
            continue
 
        if t.year != year or t.month != month:
            continue
 
        key = (year, month, t.day)
        box = day_boxes.get(key)
        if not box:
            continue

        box_h = max(1e-9, box['y1'] - box['y0'])
        y0p = box['y0'] + y_inset_frac * box_h
        y1p = box['y1'] - y_inset_frac * box_h
 
        pos = (box['row'], box['col'])
        if prev_pos is not None:
            if pos[0] != prev_pos[0] or pos[1] not in (prev_pos[1], prev_pos[1] + 1):
                flush_segment()
 
        hours = t.hour + (t.minute / 60.0) + (t.second / 3600.0)
        x = box['x0'] + (hours / 24.0) * (box['x1'] - box['x0'])
        hh = min(max(h, y_min), y_max)
        y = y0p + ((hh - y_min) / (y_max - y_min)) * (y1p - y0p)
 
        current_x.append(x)
        current_y.append(y)
        current_y0.append(y0p)
        prev_pos = pos
 
    flush_segment()
 
 
def mark_month_max_tide(fig, year, month, tide_points, day_boxes,
                        y_min=0.0, y_max=4.0,
                        marker_color='#111111', marker_size=8, border_color='white', border_width=1.0):
    month_points = [(dt, h) for (dt, h, _p) in tide_points if dt.year == year and dt.month == month]
    if not month_points:
        return
 
    max_dt, max_h = max(month_points, key=lambda x: x[1])
    box = day_boxes.get((year, month, max_dt.day))
    if not box:
        return

    y_inset_frac = 0.06
    box_h = max(1e-9, box['y1'] - box['y0'])
    y0p = box['y0'] + y_inset_frac * box_h
    y1p = box['y1'] - y_inset_frac * box_h
 
    hours = max_dt.hour + (max_dt.minute / 60.0) + (max_dt.second / 3600.0)
    x = box['x0'] + (hours / 24.0) * (box['x1'] - box['x0'])
    hh = min(max(max_h, y_min), y_max)
    y = y0p + ((hh - y_min) / (y_max - y_min)) * (y1p - y0p)
 
    fig_h_in = fig.get_size_inches()[1]
    dy = ((marker_size * 0.45) / 72.0) / fig_h_in
    y = min(y + dy, y1p - (0.5 / 72.0) / fig_h_in)
 
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
                        y_min=0.0, y_max=4.0,
                        marker_color='#111111', marker_size=8, border_color='white', border_width=1.0):
    month_points = [(dt, h) for (dt, h, _p) in tide_points if dt.year == year and dt.month == month]
    if not month_points:
        return
 
    min_dt, min_h = min(month_points, key=lambda x: x[1])
    box = day_boxes.get((year, month, min_dt.day))
    if not box:
        return

    y_inset_frac = 0.06
    box_h = max(1e-9, box['y1'] - box['y0'])
    y0p = box['y0'] + y_inset_frac * box_h
    y1p = box['y1'] - y_inset_frac * box_h
 
    hours = min_dt.hour + (min_dt.minute / 60.0) + (min_dt.second / 3600.0)
    x = box['x0'] + (hours / 24.0) * (box['x1'] - box['x0'])
    hh = min(max(min_h, y_min), y_max)
    y = y0p + ((hh - y_min) / (y_max - y_min)) * (y1p - y0p)
 
    fig_h_in = fig.get_size_inches()[1]
    dy = ((marker_size * 0.45) / 72.0) / fig_h_in
    y = max(y - dy, y0p + (0.5 / 72.0) / fig_h_in)
 
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
 
# Mark the highest and lowest tides
mark_month_max_tide(fig, year, month, tide_points, day_boxes)
mark_month_min_tide(fig, year, month, tide_points, day_boxes)
 
 
# --- Footer notes ---
footer_gap_cm = 0.5
footer_y = (cards_top_y - num_rows * (card_height_frac + row_gap_y_frac)) - (footer_gap_cm / fig_height_cm)
footer_y = max(footer_y, 0.02)
 
print(f"Footer Y position: {footer_y}")
 
# Draw upward triangle icon and label
footer_marker_size = 6
footer_marker_color = '#111111'
footer_marker_edge = 'white'
footer_marker_edgewidth = 1.0
footer_text = "Highest tide of the month"
 
# Highest tide marker
fig.add_artist(
    plt.Line2D(
        [label_side_gap_frac + 0.003], [footer_y],
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
 
footer_high_text = fig.text(
    label_side_gap_frac + 0.013, footer_y,
    footer_text,
    ha='left', va='center',
    color='#222', fontsize=9, zorder=20
)
 
# Downward triangle and text for lowest tide
footer_low_y = footer_y - 0.018
fig.add_artist(
    plt.Line2D(
        [label_side_gap_frac + 0.003], [footer_low_y],
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
    label_side_gap_frac + 0.013, footer_low_y,
    "Lowest tide of the month",
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

    # Determine the right edge of the moon column
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for t in moon_label_artists:
        bb = t.get_window_extent(renderer=renderer)
        (x1, _y1) = fig.transFigure.inverted().transform((bb.x1, bb.y1))
        moon_right_x = max(moon_right_x, x1)

    # Sunrise/Sunset key: stacked like moon, to the right of moon column
    sun_x = moon_right_x + (1.0 / fig_width_cm)

    # Pre-measure max label width so we can clamp the column inside the page
    fs_sun = 9
    tmp_sunrise = fig.text(0, 0, 'Sunrise', fontsize=fs_sun, alpha=0, weight='bold', transform=fig.transFigure)
    tmp_sunset = fig.text(0, 0, 'Sunset', fontsize=fs_sun, alpha=0, weight='bold', transform=fig.transFigure)
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    sunrise_w = tmp_sunrise.get_window_extent(renderer=renderer).width / fig.bbox.width
    sunset_w = tmp_sunset.get_window_extent(renderer=renderer).width / fig.bbox.width
    tmp_sunrise.remove()
    tmp_sunset.remove()

    sun_marker_gap = (0.18 / fig_width_cm)
    sun_col_w = sun_marker_gap + max(sunrise_w, sunset_w)
    sun_x = min(sun_x, content_right_limit_x - sun_col_w)

    sun_label_artists = []
    sun_right_x = sun_x
    sun_rows = [
        ('Sunrise', '$↑$', '#CC5500', footer_y),
        ('Sunset', '$↓$', '#4A6FA5', footer_y - ((icon_cm + icon_gap_y_cm) / fig_height_cm)),
    ]

    for label_txt, marker_txt, color_txt, yy in sun_rows:
        fig.add_artist(
            plt.Line2D(
                [sun_x], [yy],
                transform=fig.transFigure,
                linestyle='None',
                marker=marker_txt,
                markersize=footer_marker_size,
                markerfacecolor=color_txt,
                markeredgecolor=color_txt,
                markeredgewidth=footer_marker_edgewidth,
                zorder=21,
            )
        )

        sun_label = fig.text(
            sun_x + sun_marker_gap, yy,
            label_txt,
            ha='left', va='center',
            color=color_txt, fontsize=9, weight='bold', zorder=21
        )
        sun_label_artists.append(sun_label)

    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for t in sun_label_artists:
        bb = t.get_window_extent(renderer=renderer)
        (x1, _y1) = fig.transFigure.inverted().transform((bb.x1, bb.y1))
        sun_right_x = max(sun_right_x, x1)

    # Place copyright + disclaimer block to the right of the last (widest) column
    right_block_x = max(moon_right_x, sun_right_x) + (2 / fig_width_cm)
    right_block_x = min(right_block_x, content_right_limit_x)

    copyright_label = "© Copyright"
    copyright_value = "Pacific Community SPC"
    disclaimer_label = "Disclaimer"
    disclaimer_value = (
        "These tide predictions are supplied in good faith and are believed to be correct. "
        "They are not necessarily related to a local hydrographic chart datum. "
        "\n"
        "\n"
        "No warranty is given in respect to errors, omissions, or suitability for any purpose."
    )

    fs = 8
    fig_h_in = fig.get_size_inches()[1]
    line_h = ((fs * 1.2) / 72.0) / fig_h_in

    # Compute a colon x-position so both ':' align vertically
    tmp1 = fig.text(0, 0, copyright_label, fontsize=fs, alpha=0, weight='bold', transform=fig.transFigure)
    tmp2 = fig.text(0, 0, disclaimer_label, fontsize=fs, alpha=0, weight='bold', transform=fig.transFigure)
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
    wrap_chars = max(35, int(avail_px / avg_char_px * 1.2))
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
 
# Save the figure as a .pdf file
fig.savefig('tidal_calendar_with_USNO_Moon.pdf', format='pdf', bbox_inches='tight')
print("PDF saved successfully as tidal_calendar_with_USNO_Moon.pdf")