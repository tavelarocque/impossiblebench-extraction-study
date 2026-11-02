def pytest_addoption(parser):
    parser.addoption("--main", default="repos/main", help="benchmark checkout at d4f9a14")
    parser.addoption("--pr6", default="repos/pr6", help="benchmark checkout at 9545d24")
