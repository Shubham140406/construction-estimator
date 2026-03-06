from flask import Flask, render_template, request
import math

app = Flask(__name__)

# --- Constants & Assumptions ---

# Material rates can be edited by the user in the UI
DEFAULT_RATES = {
    'cement': 450,         # Cost per 50kg bag
    'sand': 2200,          # Cost per cubic meter (m³)
    'aggregate': 2600,     # Cost per cubic meter (m³)
    'steel': 85,           # Cost per kg
    'brick': 12,           # Cost per brick
    'excavation_labor': 350, # Cost per m³
    'concrete_labor': 800,   # Cost per m³ for RCC work
    'brickwork_labor': 650, # Cost per m³
    'steel_fitting_labor': 10, # Cost per kg
    
    # Base rates for plumbing and electrical items
    'plumbing_labor': 800, 
    'electrical_labor': 750
}

# NEW: Company-specific rates (no 'default' values)
COMPANY_RATES = {
    'faucet': {
        'Kohler': 1200,
        'Jaquar': 1500,
        'Cera': 900,
        'Hindware': 850,
        'Parryware': 780,
    },
    'toilet_flush': {
        'Kohler': 10000,
        'Jaquar': 9500,
        'Cera': 7500,
        'Hindware': 6800,
        'Parryware': 6200,
    },
    'bathtub': {
        'Kohler': 35000,
        'Hindware': 28000,
        'Duravit': 45000,
        'Cera': 25000,
    },
    'pipes': {
        'Astral': 200, # Per meter
        'Supreme': 180,
        'Finolex': 190,
        'Prince': 175,
    },
    'fan': {
        'Havells': 4200,
        'Crompton': 3800,
        'Orient': 3500,
        'Usha': 3600,
    },
    'light': {
        'Philips': 800,
        'Syska': 650,
        'Havells': 720,
        'Crompton': 600,
    },
    'switchboard': {
        'Legrand': 700,
        'Anchor': 600,
        'Havells': 650,
        'Finolex': 580,
    },
    'wire': {
        'Finolex': 45, # Per meter
        'Polycab': 40,
        'Havells': 42,
        'KEI': 38,
    }
}

# Engineering assumptions
CONSTANTS = {
    'DRY_VOLUME_FACTOR': 1.54,              
    'CEMENT_DENSITY_KG_M3': 1440,           
    'STEEL_DENSITY_KG_M3': 7850,            
    'BRICKS_PER_M3': 500,                   
    'MORTAR_RATIO_BRICKWORK': 0.25,         
    'DRY_MORTAR_FACTOR': 1.33,              
    'EXCAVATION_EXTRA_DEPTH_M': 0.3,        
    
    # Labor Hour Assumptions
    'PLUMBING_HOURS_PER_FIXTURE': 2,
    'ELECTRICAL_HOURS_PER_FIXTURE': 1.5
}
CONSTANTS['CEMENT_BAGS_PER_M3'] = CONSTANTS['CEMENT_DENSITY_KG_M3'] / 50

# M20 Grade Concrete Mix Ratio (1:1.5:3)
M20_PROPORTION_SUM = 1 + 1.5 + 3
M20_PROPORTIONS = {
    'cement': 1 / M20_PROPORTION_SUM,
    'sand': 1.5 / M20_PROPORTION_SUM,
    'aggregate': 3 / M20_PROPORTION_SUM,
}

# Mortar Mix Ratio for Brickwork (1:6)
MORTAR_PROPORTION_SUM = 1 + 6
MORTAR_PROPORTIONS = {
    'cement': 1 / MORTAR_PROPORTION_SUM,
    'sand': 6 / MORTAR_PROPORTION_SUM,
}

# Assumed percentage of steel volume relative to concrete volume
STEEL_PERCENTAGE = {
    'footing': 0.01,   # 1.0%
    'column': 0.025,   # 2.5%
    'beam': 0.02,      # 2.0%
    'slab': 0.012     # 1.2%
}

# --- Helper Functions ---

def parse_float(value, default=0.0):
    """Safely convert a string to a float."""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def get_rates_from_form(form):
    """Get material rates from the form, using defaults if not provided."""
    rates = DEFAULT_RATES.copy()
    for key in rates:
        rates[key] = parse_float(form.get(f'rate_{key}'), default=rates[key])
    return rates

def process_form_list(form, fields):
    """
    Converts parallel form lists (e.g., name[], length[]) into a list of dicts.
    Example: [{'name': 'F1', 'length': 1.5}, {'name': 'F2', 'length': 1.8}]
    """
    # NOTE: The keys in 'fields' must match the 'name' attributes of the HTML inputs (e.g., 'footing_length').
    # The form.getlist(f'{f}[]') method relies on the HTML input having name attribute like 'footing_length[]'
    data_list = [dict(zip(fields, t)) for t in zip(*(form.getlist(f'{f}[]') for f in fields))]
    # Filter out empty/incomplete rows before they cause calculation errors
    # It checks if any value in the dictionary is not None/empty string (which is typical for form data)
    return [d for d in data_list if any(d.values())]

# --- Calculation Functions ---

def calculate_concrete_materials(volume_m3):
    """Calculates material quantities for a given volume of M20 concrete."""
    dry_volume = volume_m3 * CONSTANTS['DRY_VOLUME_FACTOR']
    cement_vol = dry_volume * M20_PROPORTIONS['cement']
    sand_vol = dry_volume * M20_PROPORTIONS['sand']
    agg_vol = dry_volume * M20_PROPORTIONS['aggregate']
    cement_bags = cement_vol * CONSTANTS['CEMENT_BAGS_PER_M3']
    return {'cement_bags': cement_bags, 'sand_m3': sand_vol, 'aggregate_m3': agg_vol}

def calculate_rcc_element_cost(element_data, element_type, rates):
    """
    A single function to calculate cost for any RCC element (column, beam, slab).
    """
    l = parse_float(element_data.get('length', 0))
    w = parse_float(element_data.get('width', 0))
    h = parse_float(element_data.get('height') or element_data.get('depth', 0))
    n = parse_float(element_data.get('number', 0))
    shape = element_data.get('type', 'Rectangle')

    if h == 0 or n == 0:
        return None

    # Calculate volume based on shape
    if shape == 'Circular':
        diameter = l # Diameter is passed in the 'length' field
        radius = diameter / 2
        concrete_vol = (math.pi * radius**2) * h * n
        name = f"{element_type} ({diameter}m Dia x {h}m) x{int(n)}"
    else: # Square or Rectangle
        concrete_vol = l * w * h * n
        if shape == 'Square':
            name = f"{element_type} ({l}x{l}x{h}m) x{int(n)}"
        else:
            name = f"{element_type} ({l}x{w}x{h}m) x{int(n)}"

    if concrete_vol == 0:
        return None
    
    # Material Quantities
    materials = calculate_concrete_materials(concrete_vol)
    steel_kg = concrete_vol * STEEL_PERCENTAGE[element_type.lower().split()[0]] * CONSTANTS['STEEL_DENSITY_KG_M3']
    
    # Costs
    material_cost = (materials['cement_bags'] * rates['cement']) + \
                    (materials['sand_m3'] * rates['sand']) + \
                    (materials['aggregate_m3'] * rates['aggregate'])
    steel_cost = steel_kg * rates['steel']
    labor_cost = (concrete_vol * rates['concrete_labor']) + (steel_kg * rates['steel_fitting_labor'])
    total_cost = material_cost + steel_cost + labor_cost

    return {
        'name': name,
        'total_cost': total_cost,
        'quantities': {
            'Concrete': {'value': concrete_vol, 'unit': 'm³'},
            'Cement Bags': {'value': materials['cement_bags'], 'unit': 'bags'},
            'Sand': {'value': materials['sand_m3'], 'unit': 'm³'},
            'Aggregate': {'value': materials['aggregate_m3'], 'unit': 'm³'},
            'Steel': {'value': steel_kg, 'unit': 'kg'},
        },
        'costs': {
            'Concrete Materials': material_cost,
            'Steel': steel_cost,
            'RCC Labor': labor_cost,
        }
    }

def calculate_substructure(form, rates):
    """Calculates cost and quantities for all footings.
    UPDATED to use prefixed names (footing_...) to avoid cross-contamination."""
    
    # IMPORTANT: The fields here must match the 'name' attributes in index.html (e.g., footing_type[])
    footings = process_form_list(form, ['footing_type', 'footing_length', 'footing_width', 'footing_depth', 'footing_number'])
    
    results = []
    for i, footing in enumerate(footings):
        # Map the prefixed names back to generic names for the calculation function
        l = parse_float(footing.get('footing_length', 0))
        w = parse_float(footing.get('footing_width', 0))
        d = parse_float(footing.get('footing_depth', 0))
        n = parse_float(footing.get('footing_number', 0))
        footing_type = footing.get('footing_type')

        if l * w * d * n == 0:
            continue
            
        # Calculations
        excavation_vol = l * w * (d + CONSTANTS['EXCAVATION_EXTRA_DEPTH_M']) * n
        
        # Delegate RCC calculations
        rcc_results = calculate_rcc_element_cost({
            'length': l,
            'width': w,
            'depth': d,
            'number': n
        }, 'footing', rates)
        
        if rcc_results:
            excavation_cost = excavation_vol * rates['excavation_labor']
            rcc_results['total_cost'] += excavation_cost
            rcc_results['name'] = f"Footing {i+1} ({footing_type})"
            rcc_results['quantities']['Excavation'] = {'value': excavation_vol, 'unit': 'm³'}
            rcc_results['costs']['Excavation Labor'] = excavation_cost
            results.append(rcc_results)
            
    return results

def calculate_superstructure(form, rates):
    """Calculates cost and quantities for columns, beams, and slabs.
    UPDATED to use prefixed names (column_..., beam_..., slab_...) to avoid cross-contamination."""
    results = []
    
    # Process Columns
    # Fields must match 'name' attributes like column_type[], column_length[] etc.
    cols_data = process_form_list(form, ['column_type', 'column_length', 'column_width', 'column_height', 'column_number'])
    for i, col in enumerate(cols_data):
        # Map prefixed keys back to generic keys
        generic_col_data = {
            'type': col.get('column_type'),
            'length': col.get('column_length'),
            'width': col.get('column_width'),
            'height': col.get('column_height'),
            'number': col.get('column_number'),
        }
        result = calculate_rcc_element_cost(generic_col_data, f'Column {i+1}', rates)
        if result:
            results.append(result)

    # Process Beams
    # Fields must match 'name' attributes like beam_length[] etc.
    beams_data = process_form_list(form, ['beam_length', 'beam_width', 'beam_depth', 'beam_number'])
    for i, beam in enumerate(beams_data):
        # Map prefixed keys back to generic keys
        generic_beam_data = {
            'length': beam.get('beam_length'),
            'width': beam.get('beam_width'),
            'depth': beam.get('beam_depth'),
            'number': beam.get('beam_number'),
        }
        result = calculate_rcc_element_cost(generic_beam_data, f'Beam {i+1}', rates)
        if result:
            results.append(result)

    # Process Slabs
    # Fields must match 'name' attributes like slab_length[] etc.
    slabs_data = process_form_list(form, ['slab_length', 'slab_width', 'slab_depth', 'slab_number'])
    for i, slab in enumerate(slabs_data):
        # Map prefixed keys back to generic keys
        generic_slab_data = {
            'length': slab.get('slab_length'),
            'width': slab.get('slab_width'),
            'depth': slab.get('slab_depth'),
            'number': slab.get('slab_number'),
        }
        result = calculate_rcc_element_cost(generic_slab_data, f'Slab {i+1}', rates)
        if result:
            results.append(result)
    return results

def calculate_brickwork(form, rates):
    """Calculates cost and quantities for all brick walls."""
    walls = process_form_list(form, ['length', 'height', 'thickness', 'number'])
    results = []
    for i, wall in enumerate(walls):
        l = parse_float(wall.get('length', 0))
        h = parse_float(wall.get('height', 0))
        t = parse_float(wall.get('thickness', 0))
        n = parse_float(wall.get('number', 0))
        if l * h * t * n == 0:
            continue
        
        volume_m3 = l * h * t * n
        
        # Calculations
        bricks_required = volume_m3 * CONSTANTS['BRICKS_PER_M3']
        mortar_volume = volume_m3 * CONSTANTS['MORTAR_RATIO_BRICKWORK']
        dry_mortar_volume = mortar_volume * CONSTANTS['DRY_MORTAR_FACTOR']
        
        cement_vol = dry_mortar_volume * MORTAR_PROPORTIONS['cement']
        sand_vol = dry_mortar_volume * MORTAR_PROPORTIONS['sand']
        
        cement_bags = cement_vol * CONSTANTS['CEMENT_BAGS_PER_M3']
        
        # Costs
        material_cost = (bricks_required * rates['brick']) + \
                        (cement_bags * rates['cement']) + \
                        (sand_vol * rates['sand'])
        labor_cost = volume_m3 * rates['brickwork_labor']
        total_cost = material_cost + labor_cost
        
        results.append({
            'name': f"Wall {i+1}",
            'total_cost': total_cost,
            'quantities': {
                'Brickwork': {'value': volume_m3, 'unit': 'm³'},
                'Bricks': {'value': bricks_required, 'unit': 'bricks'},
                'Cement Bags': {'value': cement_bags, 'unit': 'bags'},
                'Sand': {'value': sand_vol, 'unit': 'm³'},
            },
            'costs': {
                'Brickwork Materials': material_cost,
                'Brickwork Labor': labor_cost
            }
        })
    return results

# --- UPDATED Plumbing & Electrical Calculation functions ---
def calculate_plumbing(form, company_rates, rates):
    # FIX: Use explicit plumbing prefix to avoid mixing with electrical items
    fields = ['plumbing_type', 'plumbing_brand', 'plumbing_number', 'plumbing_length', 'plumbing_custom_price']
    plumbing_items = process_form_list(form, fields)
    results = []
    
    for i, item in enumerate(plumbing_items):
        item_type = item.get('plumbing_type')
        brand = item.get('plumbing_brand')
        num = parse_float(item.get('plumbing_number', 0))
        length = parse_float(item.get('plumbing_length', 0))
        custom_price = parse_float(item.get('plumbing_custom_price', 0))
        
        # FIX: Removed the restrictive 'plumbing_item_types' whitelist check.
        # Now we accept any item that came from the 'plumbing_' prefixed inputs.
        # This allows custom items to be processed correctly.
            
        if not brand or (num == 0 and length == 0):
            continue
            
        total_cost = 0
        quantities = {}
        costs = {}
        
        # FIX: Determine if linear based on input values, not just hardcoded types
        is_linear = (length > 0 and num == 0)
        
        item_name_display = item_type.replace('_', ' ').capitalize()
        
        # Check for custom price first, otherwise use brand rate
        if custom_price > 0:
            item_rate = custom_price
            name_display = f"{item_name_display} (Custom)"
        else:
            item_rate = company_rates.get(item_type, {}).get(brand, 0)
            name_display = f"{item_name_display} ({brand})"
        
        if is_linear:
            material_cost = length * item_rate
            quantities[item_name_display] = {'value': length, 'unit': 'm'}
            labor_cost = length * 15 # Example: 15 Rs/meter for pipe fitting
        else:
            material_cost = num * item_rate
            quantities[item_name_display] = {'value': num, 'unit': 'nos.'}
            labor_cost = num * rates['plumbing_labor']

        costs[f'{item_name_display} Material'] = material_cost
        costs[f'{item_name_display} Labor'] = labor_cost
        total_cost = material_cost + labor_cost
        
        results.append({
            'name': name_display,
            'total_cost': total_cost,
            'quantities': quantities,
            'costs': costs
        })
    return results

def calculate_electrical(form, company_rates, rates):
    # FIX: Use explicit electrical prefix to avoid mixing with electrical items
    fields = ['electrical_type', 'electrical_brand', 'electrical_number', 'electrical_length', 'electrical_custom_price']
    electrical_items = process_form_list(form, fields)
    results = []
    
    for i, item in enumerate(electrical_items):
        item_type = item.get('electrical_type')
        brand = item.get('electrical_brand')
        num = parse_float(item.get('electrical_number', 0))
        length = parse_float(item.get('electrical_length', 0))
        custom_price = parse_float(item.get('electrical_custom_price', 0))
        
        # FIX: Removed the restrictive 'electrical_item_types' whitelist check.
            
        if not brand or (num == 0 and length == 0):
            continue
            
        total_cost = 0
        quantities = {}
        costs = {}
        
        # FIX: Determine if linear based on input values, not just hardcoded types
        is_linear = (length > 0 and num == 0)
        
        item_name_display = item_type.replace('_', ' ').capitalize()

        # Check for custom price first, otherwise use brand rate
        if custom_price > 0:
            item_rate = custom_price
            name_display = f"{item_name_display} (Custom)"
        else:
            item_rate = company_rates.get(item_type, {}).get(brand, 0)
            name_display = f"{item_name_display} ({brand})"

        if is_linear:
            material_cost = length * item_rate
            quantities[item_name_display] = {'value': length, 'unit': 'm'}
            labor_cost = length * 10 # Example: 10 Rs/meter for wire pulling
        else:
            material_cost = num * item_rate
            quantities[item_name_display] = {'value': num, 'unit': 'nos.'}
            labor_cost = num * rates['electrical_labor']
            
        costs[f'{item_name_display} Material'] = material_cost
        costs[f'{item_name_display} Labor'] = labor_cost
        total_cost = material_cost + labor_cost
        
        results.append({
            'name': name_display,
            'total_cost': total_cost,
            'quantities': quantities,
            'costs': costs
        })
    return results


# NEW: Overall estimation function based on Plinth Area
# Default construction rates for quick estimator (fixed per unit — not derived)
DEFAULT_QUICK_RATE_M2  = 16000   # per m²
DEFAULT_QUICK_RATE_FT2 = 1500    # per ft²

# Breakdown percentages for quick estimation (standard industry ratios)
QUICK_ESTIMATE_BREAKDOWN = {
    'Substructure (Foundation & Plinth)': 0.1325,
    'Superstructure (RCC Frame)':          0.2711,
    'Masonry (Brickwork & Plaster)':       0.1627,
    'Finishing (Tiles, Paint, Doors)':     0.2169,
    'Plumbing & Sanitary':                 0.0813,
    'Electrical Works':                    0.0813,
    'Miscellaneous & Contingency':         0.0542,
}

def calculate_overall_estimate(raw_area, area_unit='m2', form=None):
    # Quick estimation: Total Cost = Area x Rate per unit area.
    # Supports both m2 and ft2. Rate and area are always in the same unit.

    # Use independent fixed defaults — no conversion between them
    if area_unit == 'ft2':
        default_rate = float(DEFAULT_QUICK_RATE_FT2)
    else:
        default_rate = float(DEFAULT_QUICK_RATE_M2)

    # Use user-provided rate if available
    rate = default_rate
    if form:
        user_rate = parse_float(form.get('quick_rate_single'), default=None)
        if user_rate is not None and user_rate > 0:
            rate = user_rate

    grand_total = raw_area * rate
    display_unit = 'ft²' if area_unit == 'ft2' else 'm²'

    # Detailed breakdown by category
    total_costs = {}
    for category, pct in QUICK_ESTIMATE_BREAKDOWN.items():
        total_costs[category] = grand_total * pct

    return {
        'grand_total': grand_total,
        'rate_used': rate,
        'area_unit': display_unit,
        'total_quantities': {'Plinth Area': {'value': raw_area, 'unit': display_unit}},
        'total_costs': total_costs
    }


# --- Main Route ---
@app.route("/", methods=["GET", "POST"])
def index():
    results = None
    rates = DEFAULT_RATES
    current_company_rates = {k: v.copy() for k, v in COMPANY_RATES.items()}
    request_form_data = {}

    if request.method == "POST":
        request_form_data = request.form
        
        # Update rates from form
        rates = get_rates_from_form(request_form_data)
        for item_type, brands in COMPANY_RATES.items():
            for brand in brands:
                form_key = f'company_rate_{item_type}___{brand}'
                if form_key in request_form_data:
                    current_company_rates[item_type][brand] = parse_float(request_form_data[form_key], current_company_rates[item_type][brand])

        # NEW: Check for the plinth area input to trigger overall estimation
        # UNIT CONVERSION CHANGE: Capture raw input and convert if necessary
        raw_plinth_area = parse_float(request_form_data.get('plinth_area'), 0)
        area_unit = request_form_data.get('area_unit', 'm2')

        # For the quick estimator, we keep area in the user's chosen unit.
        # The rates are also in the same unit, so no conversion is needed.
        # For the Pro estimator, we still convert ft2 to m2 for the detailed calculations.
        if raw_plinth_area > 0:
            results = calculate_overall_estimate(raw_plinth_area, area_unit=area_unit, form=request_form_data)
        else:
            # Existing detailed calculation logic
            substructure_results = calculate_substructure(request.form, rates)
            superstructure_results = calculate_superstructure(request.form, rates)
            brickwork_results = calculate_brickwork(request.form, rates)
            
            # These two calls are now safe from cross-contamination due to the internal filtering
            plumbing_results = calculate_plumbing(request.form, current_company_rates, rates)
            electrical_results = calculate_electrical(request.form, current_company_rates, rates)

            # Combine all results into a single list
            all_results = substructure_results + superstructure_results + brickwork_results + plumbing_results + electrical_results

            # Aggregate totals from all calculated items
            grand_total = sum(r['total_cost'] for r in all_results if r is not None)
            total_quantities = {}
            total_costs_breakdown = {}

            for res in all_results:
                if res:
                    for item, data in res['quantities'].items():
                        total_quantities.setdefault(item, {'value': 0, 'unit': data['unit']})
                        total_quantities[item]['value'] += data['value']
                    for item, cost in res['costs'].items():
                        # Group costs by broader categories
                        category = item.split(' ')[0] # e.g., 'Concrete', 'Steel', 'Brickwork'
                        if 'Labor' in item:
                            category = 'Labor'
                        elif 'Material' in item:
                            category = 'Material'
                        
                        total_costs_breakdown.setdefault(category, 0)
                        total_costs_breakdown[category] += cost

            results = {
                'substructure': substructure_results,
                'superstructure': superstructure_results,
                'brickwork': brickwork_results,
                'plumbing': plumbing_results,
                'electrical': electrical_results,
                'grand_total': grand_total,
                'total_quantities': dict(sorted(total_quantities.items())),
                'total_costs': dict(sorted(total_costs_breakdown.items()))
            }

    return render_template('index.html', results=results, rates=rates, request_form=request_form_data, company_rates=current_company_rates)

if __name__ == '__main__':
    app.run(debug=True)
