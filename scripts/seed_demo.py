from backend.app.config import Settings
from backend.app.seed import seed
from backend.app.services.hub import Hub


def main():
    hub = Hub(Settings())
    seed(hub)
    print("演示种子已幂等初始化；已有修改不会被覆盖。演示账号禁止公网使用。")


if __name__ == "__main__":
    main()
