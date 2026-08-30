import os

from monday_client import MondayClient
from normalize import build_quality_summary, normalize_deals, normalize_work_orders
from agent import create_agent


def main():
    print("=" * 60)
    print("LOADING MONDAY.COM DATA")
    print("=" * 60)

    client = MondayClient()

    work_order_id = os.getenv("WORK_ORDER_BOARD_ID")
    deal_id = os.getenv("DEAL_FUNNEL_BOARD_ID")

    work_orders = client.board_to_dataframe(work_order_id)
    deals = client.board_to_dataframe(deal_id)

    print(f"Work orders loaded: {len(work_orders)}")
    print(f"Deals loaded: {len(deals)}")

    work_orders = normalize_work_orders(work_orders)
    deals = normalize_deals(deals)

    work_quality = build_quality_summary(work_orders)
    deal_quality = build_quality_summary(deals)

    ask = create_agent(
        deals_df=deals,
        work_orders_df=work_orders,
        work_order_quality=work_quality,
        deal_quality=deal_quality,
    )

    questions = [
        "How is our Mining pipeline looking?",
        "What are the financials for Mining work orders?",
        "Compare Mining deal pipeline with work-order execution.",
        "Compare deal pipeline with work-order execution.",
        "How much revenue do we have?",
    ]

    for i, question in enumerate(questions, start=1):
        print("\n")
        print("=" * 60)
        print(f"TEST {i}")
        print("=" * 60)

        print("QUESTION:")
        print(question)

        print("\nANSWER:")

        try:
            answer = ask(question)
            print(answer)
        except Exception as e:
            print("ERROR:")
            print(e)


if __name__ == "__main__":
    main()
