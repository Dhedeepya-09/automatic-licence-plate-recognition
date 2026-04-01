from datetime import datetime
import pytz
from database import get_vehicle_details, log_challan

IST = pytz.timezone('Asia/Kolkata')

# Fine Constants
FINE_PUC = 1000
FINE_OLD_VEHICLE = 5000
FINE_SMOKE = 2000
MAX_VEHICLE_AGE = 15

def check_violations(plate_number, detected_smoke=False):
    """Checks for PUC, Age, and Smoke violations."""
    vehicle_details = get_vehicle_details(plate_number)
    violations = []
    total_fine = 0
    
    if not vehicle_details:
        # If vehicle not in RTO, it's an Unregistered vehicle violation
        violations.append("Unregistered Vehicle")
        total_fine += 5000
        return violations, total_fine, "Unknown"

    plate, owner, v_type, reg_year, puc_expiry = vehicle_details
    now_ist = datetime.now(IST)
    current_year = now_ist.year
    
    # 1. PUC Expiry Check
    puc_date = datetime.strptime(puc_expiry, '%Y-%m-%d').replace(tzinfo=IST)
    if puc_date < now_ist:
        violations.append("Expired PUC Certificate")
        total_fine += FINE_PUC
        
    # 2. Old Vehicle Check
    if (current_year - reg_year) > MAX_VEHICLE_AGE:
        violations.append(f"Vehicle Over {MAX_VEHICLE_AGE} Years Old")
        total_fine += FINE_OLD_VEHICLE
        
    # 3. Smoke Violation
    if detected_smoke:
        violations.append("Excessive Smoke Emission Detected")
        total_fine += FINE_SMOKE
        
    # Log Challan if any violation occurred
    if violations:
        violation_str = ", ".join(violations)
        log_challan(plate, violation_str, total_fine)
        
    return violations, total_fine, owner

def get_summary_stats(all_challans):
    """Returns basic stats for the dashboard."""
    stats = {
        'total_violations': len(all_challans),
        'total_fines': sum(c[3] for c in all_challans),
        'puc_violations': sum(1 for c in all_challans if "PUC" in c[2]),
        'smoke_violations': sum(1 for c in all_challans if "Smoke" in c[2])
    }
    return stats
