import datetime
import csv
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

def load_tide_extrema(file_path: Path):
    points = []
    if not file_path.exists():
        return points
    with file_path.open('r', encoding='utf-8', errors='ignore', newline='') as f:
        # Detect CSV header format: time,tidal_peaks,type
        first_pos = f.tell()
        first_line = f.readline().strip()
        f.seek(first_pos)

        if first_line.lower().startswith('time,'):
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    dt = datetime.datetime.fromisoformat((row.get('time') or '').strip())
                    height = float((row.get('tidal_peaks') or '').strip())
                    phase = ((row.get('type') or '').strip()[:1].upper())
                except Exception:
                    continue
                points.append((dt, height, phase))
        else:
            # Legacy simple CSV-like format: ISO_DATETIME,HEIGHT[,PHASE]
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


DATA_FILE = 'FSM_583010_Pohnpei_hlw_2027_2028_ltz_feet.csv'
tide_points = load_tide_extrema(Path(__file__).with_name(DATA_FILE))

available_years = sorted({dt.year for (dt, _h, _ph) in tide_points})
if tide_points:
    min_dt = min(tide_points, key=lambda x: x[0])[0]
    max_dt = max(tide_points, key=lambda x: x[0])[0]
    print(f"Loaded {len(tide_points)} extrema from {DATA_FILE}")
    print(f"Coverage: {min_dt.isoformat()} → {max_dt.isoformat()} | Years: {available_years}")

# Set YEAR to a specific calendar year (e.g. 2027) or set to None to use all rows in the file.
# Note: the provided Suva file only has one day in 2026 (Dec 31), so YEAR=2026 will yield ~1 H and ~1 L.
YEAR = 2027

if YEAR is None:
    tide_points_year = tide_points
else:
    tide_points_year = [p for p in tide_points if p[0].year == YEAR]

high_candidates = [p for p in tide_points_year if (p[2] or '').upper() == 'H']
low_candidates = [p for p in tide_points_year if (p[2] or '').upper() == 'L']

high_tides = sorted(high_candidates, key=lambda x: -x[1])[:10]
low_tides = sorted(low_candidates, key=lambda x: x[1])[:10]

if YEAR is not None and len(tide_points_year) < 100:
    print(
        f"Warning: only {len(tide_points_year)} records match YEAR={YEAR}. "
        "This usually means the source file doesn't contain that full year."
    )

header = ['Date', 'Time', 'Height (ft)']

high_rows = [[dt.strftime('%d-%b'), dt.strftime('%I:%M %p'), f'{h:.2f}']
             for dt, h, _ in high_tides]

low_rows = [[dt.strftime('%d-%b'), dt.strftime('%I:%M %p'), f'{h:.2f}']
            for dt, h, _ in low_tides]

# Combine side by side
side_by_side_header = header + header
side_by_side_rows = []

for i in range(10):
    left = high_rows[i] if i < len(high_rows) else ['', '', '']
    right = low_rows[i] if i < len(low_rows) else ['', '', '']
    side_by_side_rows.append(left + right)

# Export CSV alongside the PNG (same side-by-side layout)
csv_suffix = f"{YEAR}" if YEAR is not None else "all"
csv_out = Path(__file__).with_name(f'top10_tides_table_{csv_suffix}.csv')
with csv_out.open('w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow([
        f'10 highest tides for {csv_suffix}', '', '',
        f'10 lowest tides for {csv_suffix}', '', '',
    ])
    writer.writerow([
        'High Date', 'High Time', 'High Height (m)',
        'Low Date', 'Low Time', 'Low Height (m)',
    ])
    writer.writerows(side_by_side_rows)

fig, ax = plt.subplots(figsize=(9, 4.5))
ax.axis('off')




# Build table: only data headers and rows (no group header row)
all_rows = [side_by_side_header] + side_by_side_rows



# Create table with 6 columns
table = ax.table(
    cellText=all_rows,
    loc='center',
    cellLoc='center',
    colWidths=[0.15] * 6,
)

table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 1.5)

cells = table.get_celld()

# Draw a fake two-column header with borders above the table
fig.canvas.draw()  # Needed to get correct positions
table_bbox = table.get_window_extent(fig.canvas.get_renderer())
inv = ax.transAxes.inverted()
bbox_axes = inv.transform(table_bbox)

# Calculate width and height for header rectangles
table_left = bbox_axes[0, 0]
table_right = bbox_axes[1, 0]
table_top = bbox_axes[1, 1]
table_width = table_right - table_left
header_height = 0.06  # relative axes units, adjust as needed

col_width = table_width / 2


# Draw left header rectangle with custom color
header_color = '#00aabc'
left_rect = Rectangle((table_left, table_top), col_width, header_height,
             linewidth=1.5, edgecolor=header_color, facecolor=header_color, zorder=2)
ax.add_patch(left_rect)
ax.text(table_left + col_width/2, table_top + header_height/2,
    f'10 highest tides for {csv_suffix}',
    ha='center', va='center', fontsize=12, weight='bold', zorder=3, color='white', transform=ax.transAxes)

# Draw right header rectangle with custom color
right_rect = Rectangle((table_left + col_width, table_top), col_width, header_height,
              linewidth=1.5, edgecolor=header_color, facecolor=header_color, zorder=2)
ax.add_patch(right_rect)
ax.text(table_left + col_width + col_width/2, table_top + header_height/2,
    f'10 lowest tides for {csv_suffix}',
    ha='center', va='center', fontsize=12, weight='bold', zorder=3, color='white', transform=ax.transAxes)

# Adjust layout to fit header
plt.tight_layout(rect=[0, 0, 1, 0.93])

# -----------------------------
# Styling: only first row bold
# -----------------------------

# Set header row color and border
for (row, col), cell in cells.items():
    cell.set_text_props(weight='normal')

# -----------------------------
# Styling
# -----------------------------
for (row, col), cell in cells.items():
    if row == 0:
        cell.set_text_props(weight='normal')
    if row == 1:
        cell.set_text_props(weight='normal')

# Add two big group headers above the table using ax.text
fig.canvas.draw()  # Needed to get correct positions
table_bbox = table.get_window_extent(fig.canvas.get_renderer())
inv = ax.transAxes.inverted()
bbox_axes = inv.transform(table_bbox)

# Calculate x positions for left and right group headers
left_x = 0.25
right_x = 0.75
top_y = bbox_axes[1, 1] + 0.03  # a bit above the table
"""
ax.text(left_x, top_y, f'10 highest tides for {YEAR}',
    ha='center', va='bottom', fontsize=14, weight='bold', transform=ax.transAxes)
ax.text(right_x, top_y, f'10 lowest tides for {YEAR}',
    ha='center', va='bottom', fontsize=14, weight='bold', transform=ax.transAxes)
"""
png_out = Path(__file__).with_name(f'top10_tides_table_{csv_suffix}.png')
plt.savefig(png_out, dpi=300)
# plt.show()