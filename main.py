from dataclasses import dataclass
from typing import Optional
from tabulate import tabulate

@dataclass
class PlanParams:
    current_savings: float
    annual_return_nominal: float           # e.g., 0.05 for 5%
    annual_inflation: float                # e.g., 0.03 for 3% CPI
    monthly_withdrawal: float              # fixed monthly withdrawal from savings
    target_years: int = 20                 # horizon for "required initial to last N years"
    withdrawal_timing: str = "start"       # "start" or "end" of month
    effective_tax_rate_on_returns: Optional[float] = None  # simple optional haircut
    start_age: Optional[float] = None      # optional age, used for labeling
    yearly_withdrawal: Optional[float] = None  # optional yearly withdrawal in January

    def monthly_nominal_return(self) -> float:
        """Convert nominal annual return to effective monthly return."""
        r = self.annual_return_nominal
        if self.effective_tax_rate_on_returns:
            r = r * (1 - self.effective_tax_rate_on_returns)
        return (1 + r) ** (1/12) - 1

    def annual_real_rate(self) -> float:
        """Real annual rate based on nominal return and inflation."""
        r = self.annual_return_nominal
        if self.effective_tax_rate_on_returns:
            r = r * (1 - self.effective_tax_rate_on_returns)
        g = self.annual_inflation
        return (1 + r) / (1 + g) - 1

    def monthly_real_rate(self) -> float:
        """Real monthly rate for the closed-form calculation."""
        return (1 + self.annual_real_rate()) ** (1/12) - 1


def simulate_retirement(params: PlanParams, max_years: int = 100, adjust_withdrawal_for_inflation: bool = True) -> dict:
    """
    Deterministic month-by-month simulation with inflation-adjusted monthly withdrawal if specified.
    Returns a dict with summary and a list of monthly snapshots.
    """
    balance = params.current_savings
    m_return = params.monthly_nominal_return()
    monthly_withdrawal = params.monthly_withdrawal
    yearly_withdrawal = params.yearly_withdrawal
    months = max_years * 12
    snapshots = []
    monthly_inflation = (1 + params.annual_inflation) ** (1/12) - 1
    yearly_inflation = params.annual_inflation
    adj_yearly_withdrawal = yearly_withdrawal if yearly_withdrawal is not None else 0.0

    for m in range(1, months + 1):
        # Adjust withdrawal for inflation if enabled
        if adjust_withdrawal_for_inflation and m > 1:
            monthly_withdrawal *= (1 + monthly_inflation)
            if yearly_withdrawal is not None and (m % 12 == 1):
                # Adjust yearly withdrawal for inflation each January
                adj_yearly_withdrawal *= (1 + yearly_inflation)

        # Apply withdrawal timing
        if params.withdrawal_timing == "start":
            balance -= monthly_withdrawal
            if yearly_withdrawal is not None and (m % 12 == 1):
                balance -= adj_yearly_withdrawal
        elif params.withdrawal_timing == "end":
            pass  # withdraw after growth
        else:
            raise ValueError("withdrawal_timing must be 'start' or 'end'.")

        # Calculate investment return for this month
        pre_growth_balance = balance
        balance *= (1 + m_return)
        investment_return = balance - pre_growth_balance

        if params.withdrawal_timing == "end":
            balance -= monthly_withdrawal
            if yearly_withdrawal is not None and (m % 12 == 1):
                balance -= adj_yearly_withdrawal

        age = params.start_age + (m - 1) / 12.0 if params.start_age is not None else None
        snapshots.append({
            "month_index": m,
            "age": age,
            "balance": balance,
            "monthly_withdrawal": monthly_withdrawal,
            "yearly_withdrawal": adj_yearly_withdrawal if (yearly_withdrawal is not None and (m % 12 == 1)) else 0.0,
            "monthly_return": investment_return,
        })

        if balance <= 0:
            years_lasted = (m - 1) / 12.0
            return {
                "depleted": True,
                "months_lasted": m - 1,
                "years_lasted": years_lasted,
                "final_balance": balance,
                "snapshots": snapshots
            }

    return {
        "depleted": False,
        "months_lasted": months,
        "years_lasted": months / 12.0,
        "final_balance": balance,
        "snapshots": snapshots
    }


def required_initial_for_horizon_closed_form(params: PlanParams, years: Optional[int] = None) -> float:
    """
    Closed-form present value in real terms to last N years with fixed monthly and yearly withdrawals.
    """
    N_years = years if years is not None else params.target_years
    n_months = N_years * 12
    i_m = params.monthly_real_rate()
    PMT_m = params.monthly_withdrawal
    PV_monthly = 0.0
    PV_yearly = 0.0

    # Present value of monthly withdrawals (ordinary annuity)
    if abs(i_m) < 1e-9:
        PV_monthly = PMT_m * n_months
    else:
        PV_monthly = PMT_m * (1 - (1 + i_m) ** (-n_months)) / i_m

    # Present value of yearly withdrawals (at the start of each year, i.e., months 1, 13, ...)
    if params.yearly_withdrawal is not None and params.yearly_withdrawal > 0:
        PMT_y = params.yearly_withdrawal
        i_y = (1 + i_m) ** 12 - 1  # effective real annual rate
        n_years = N_years
        # Present value of yearly withdrawals (ordinary annuity, annual payments)
        if abs(i_y) < 1e-9:
            PV_yearly = PMT_y * n_years
        else:
            PV_yearly = PMT_y * (1 - (1 + i_y) ** (-n_years)) / i_y
        # Discount yearly PV to present (if first withdrawal is at t=0, no further discount needed)

    return PV_monthly + PV_yearly


def required_initial_for_horizon_via_simulation(params: PlanParams, years: Optional[int] = None,
                                                tol: float = 1e-6, max_iter: int = 200) -> float:
    """
    Numerical solver using bisection with the month-by-month simulation.
    Finds initial savings that result in depletion at ~target years.
    """
    N_years = years if years is not None else params.target_years
    low = 0.0
    high = max(1.0, required_initial_for_horizon_closed_form(params, N_years) * 2)

    for _ in range(max_iter):
        mid = 0.5 * (low + high)
        test_params = PlanParams(**{**params.__dict__, "current_savings": mid})
        sim = simulate_retirement(test_params, max_years=N_years + 5)
        years_lasted = sim["years_lasted"]
        if years_lasted > N_years:
            high = mid
        else:
            low = mid
        if abs(high - low) <= tol * max(1.0, mid):
            return mid
    return 0.5 * (low + high)


def years_until_depletion(params: PlanParams, max_years: int = 100) -> float:
    """Convenience function to return years until depletion from the simulation."""
    sim = simulate_retirement(params, max_years=max_years)
    if sim["depleted"]:
        return sim["years_lasted"]
    else:
        # If not depleted within max_years, return that bound
        return sim["years_lasted"]


# ---- Example usage ----
if __name__ == "__main__":
    # Example: simple scenario
    p = PlanParams(
        current_savings=350_000,
        annual_return_nominal=0.125, # (Tesouro Selic/CDI after 15% IR and 0.20% custody)
        annual_inflation=0.047, # Current 12‑month IPCA
        monthly_withdrawal=4_000,
        yearly_withdrawal=30_000,  # Additional yearly withdrawal in January
        target_years=20,
        withdrawal_timing="start",
        start_age=80
    )

    yrs = years_until_depletion(p, max_years=60)
    print(f"Deterministic simulation → savings last ~{yrs:.1f} years.")

    # Print monthly simulation table using tabulate
    sim = simulate_retirement(p, max_years=60)
    table = []
    for snap in sim["snapshots"]:
        month = snap["month_index"]
        age = f"{snap['age']:.2f}" if snap["age"] is not None else "-"
        balance = f"${snap['balance']:,.2f}"
        monthly_wd = f"${snap['monthly_withdrawal']:,.2f}"
        yearly_wd = f"${snap['yearly_withdrawal']:,.2f}" if snap.get('yearly_withdrawal', 0.0) else "-"
        monthly_return = f"${snap['monthly_return']:,.2f}"
        table.append([month, age, balance, monthly_wd, yearly_wd, monthly_return])
    headers = ["Month", "Age", "Balance", "Monthly Wd", "Yearly Wd", "Monthly Return"]
    print("\n" + tabulate(table, headers=headers, tablefmt="github"))

    selected_years = 20
    req_cf = required_initial_for_horizon_closed_form(p, years=selected_years)
    print(f"Closed-form estimate → required initial to last {selected_years} years: ${req_cf:,.0f}")

    req_sim = required_initial_for_horizon_via_simulation(p, years=selected_years)
    print(f"Simulation-based required initial to last {selected_years} years: ${req_sim:,.0f}")
