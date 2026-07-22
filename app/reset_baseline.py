"""Start a clean forward-paper window without deleting research history."""
from engine import execsim, risk, setups, store


def main() -> None:
    con = store.connect()
    try:
        baseline = store.start_baseline(
            con, label="Forward paper baseline",
            strategy_version=setups.SETUP_VERSION,
            execution_version=execsim.EXEC_VERSION,
            risk_version=risk.RISK_VERSION)
        result = risk.run(con)
        print(
            f"Fresh paper baseline #{baseline['id']} started at "
            f"{baseline['started_at']}. Equity reset to ${result['final_equity']}."
        )
        print("Historical candles and facts were retained for audit.")
    finally:
        con.close()


if __name__ == "__main__":
    main()
