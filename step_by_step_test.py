"""
`main.py`의 기능들을 단계별로 실행하고 각 단계의 결과를 수동으로 검증하기 위한
개발 및 디버깅용 테스트 스크립트입니다.

이 스크립트는 자동화된 테스트가 아니라, 개발자가 애플리케이션의 초기화 과정을
한 단계씩 눈으로 확인하고 중간 객체들의 상태를 점검하는 데 도움을 줍니다.
예를 들어, `setup_exchange` 후 `exchange` 객체가 제대로 생성되었는지,
`setup_services` 후 각 서비스 객체들이 올바르게 초기화되었는지 등을 확인할 수 있습니다.

**사용 방법:**
1.  `.env` 파일에 유효한 API 키 (테스트넷 키 권장) 및 기타 설정을 입력합니다.
2.  스크립트 하단의 `if __name__ == "__main__":` 블록에서 `load_dotenv()` 주석을 해제합니다.
3.  터미널에서 `python step_by_step_test.py`를 실행합니다.
4.  각 단계(`Step 1`, `Step 2` 등)의 실행 결과를 콘솔에서 확인합니다.
5.  필요에 따라 각 단계 아래의 검증 코드 영역에 `print()`나 `assert` 구문을 추가하여
    더 상세한 내용을 확인할 수 있습니다.
"""

# main.py에서 애플리케이션 구성 요소를 초기화하는 함수들을 임포트합니다.
from main import setup_exchange, setup_services, start_bot_and_dashboard
# .env 파일 로드를 위해 load_dotenv를 임포트합니다.
from dotenv import load_dotenv

def run_step_by_step_test():
    """
    애플리케이션 초기화 과정을 단계별로 실행하고 출력합니다.
    """
    print("--- Step 1: Setting up the exchange client ---")
    # `main.py`의 `setup_exchange` 함수를 호출하여 거래소 클라이언트 객체를 생성합니다.
    exchange = setup_exchange()

    # <<< 여기에 exchange 객체 검증 코드를 추가하여 디버깅할 수 있습니다 >>>
    print(f"Exchange client type: {type(exchange.client).__name__}")
    # 예: `ccxt` 클라이언트 객체가 제대로 생성되었는지 확인
    # print(dir(exchange.client))
    # 예: `assert`를 사용하여 객체가 None이 아님을 보장
    assert exchange is not None, "Exchange object should not be None"

    print("Step 1: Exchange setup complete.")
    print("-" * 40)

    print("--- Step 2: Setting up services (IndicatorRepository, ModelService, OrderService) ---")
    # 생성된 exchange 객체를 인자로 넘겨주어 각 서비스들을 초기화합니다.
    repo, model, order = setup_services(exchange)

    # <<< 여기에 서비스 객체들(repo, model, order) 검증 코드를 추가하여 디버깅할 수 있습니다 >>>
    print(f"IndicatorRepository initialized for symbol: {repo.symbol}")
    print(f"ModelService will use model file at: {model.path}")
    print(f"OrderService is in {'Paper' if order.paper else 'Live'} mode with initial balance: {order.balance}")
    # 예: 각 서비스 객체가 정상적으로 생성되었는지 확인
    assert all([repo, model, order]), "All service objects should be initialized"

    print("Step 2: Services setup complete.")
    print("-" * 40)

    print("--- Step 3: Starting the bot's main loop and the dashboard ---")
    # 참고: 이 함수는 봇의 메인 루프를 백그라운드 스레드에서 시작하고,
    # 메인 스레드에서는 대시보드를 실행하므로, 이 함수가 호출되면 프로그램은 종료되지 않고 계속 실행됩니다.
    # 봇의 동작을 확인하려면 콘솔 로그와 함께 웹 브라우저에서 Streamlit 대시보드(일반적으로 http://localhost:8501)를
    # 확인해야 합니다.
    print("The bot loop will now start in the background.")
    print("Open your web browser to view the Streamlit dashboard.")
    start_bot_and_dashboard(repo, model, order)

    # 이 라인은 `start_bot_and_dashboard`가 UI를 실행하고 블로킹하기 때문에 일반적으로 실행되지 않습니다.
    print("Step 3: Bot and dashboard started.")
    print("-" * 40)


if __name__ == "__main__":
    # 이 스크립트를 직접 실행하기 전에 `.env` 파일의 환경 변수를 로드해야 합니다.
    # 아래 라인의 주석을 해제하세요.
    load_dotenv()

    run_step_by_step_test()
