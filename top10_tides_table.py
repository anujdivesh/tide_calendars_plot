import datetime
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

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


DATA_FILE = '66840_hlw.data'
tide_points = load_tide_extrema(Path(__file__).with_name(DATA_FILE))

YEAR = 2025
tide_points_year = [p for p in tide_points if p[0].year == YEAR]

high_tides = sorted(tide_points_year, key=lambda x: -x[1])[:10]
low_tides = sorted(tide_points_year, key=lambda x: x[1])[:10]

header = ['Date', 'Time', 'Height (m)']

high_rows = [[dt.strftime('%d-%b'), dt.strftime('%I:%M %p'), f'{h:.3f}']
             for dt, h, _ in high_tides]

low_rows = [[dt.strftime('%d-%b'), dt.strftime('%I:%M %p'), f'{h:.3f}']
            for dt, h, _ in low_tides]

# Combine side by side
side_by_side_header = header + header
side_by_side_rows = []

for i in range(10):
    left = high_rows[i] if i < len(high_rows) else ['', '', '']
    right = low_rows[i] if i < len(low_rows) else ['', '', '']
    side_by_side_rows.append(left + right)

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
    f'10 highest tides for {YEAR}',
    ha='center', va='center', fontsize=12, weight='bold', zorder=3, color='white', transform=ax.transAxes)

# Draw right header rectangle with custom color
right_rect = Rectangle((table_left + col_width, table_top), col_width, header_height,
              linewidth=1.5, edgecolor=header_color, facecolor=header_color, zorder=2)
ax.add_patch(right_rect)
ax.text(table_left + col_width + col_width/2, table_top + header_height/2,
    f'10 lowest tides for {YEAR}',
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
plt.savefig('top10_tides_table.png', dpi=300)
# plt.show()