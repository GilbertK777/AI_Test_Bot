"""
main.py의 기능들을 단계별로 실행하고 검증하기 위한 테스트 스크립트
"""

from main import setup_exchange, setup_services, start_bot_and_dashboard

def run_step_by_step_test():
    print("Step 1: Setting up the exchange...")
    exchange = setup_exchange()
    # <<< 여기에 exchange 객체 검증 코드를 추가하세요 >>>
    # 예: print(exchange)
    # 예: assert exchange is not None
    print("Step 1: Exchange setup complete.")
    print("-" * 30)

    print("Step 2: Setting up services (IndicatorRepository, ModelService, OrderService)...")
    repo, model, order = setup_services(exchange)
    # <<< 여기에 서비스 객체들(repo, model, order) 검증 코드를 추가하세요 >>>
    # 예: print(repo)
    # 예: print(model)
    # 예: print(order)
    # 예: assert repo is not None and model is not None and order is not None
    print("Step 2: Services setup complete.")
    print("-" * 30)

    print("Step 3: Starting the bot and dashboard...")
    # 참고: 이 함수는 봇의 메인 루프를 백그라운드 스레드에서 시작하고
    # 대시보드를 실행하므로, 호출하면 프로그램이 계속 실행됩니다.
    start_bot_and_dashboard(repo, model, order)
    print("Step 3: Bot and dashboard started.")
    print("-" * 30)


if __name__ == "__main__":
    # .env 파일이 있는지 확인하고 로드하는 것이 좋습니다.
    # from dotenv import load_dotenv
    # load_dotenv()
    run_step_by_step_test()
