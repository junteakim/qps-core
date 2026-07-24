# Contributing

## Development

Create an isolated Python environment, install the development dependencies, and run the complete test suite before submitting a change.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
python scripts/verify_public_release.py .
```

## Fixture policy

Use invented organizations, identifiers, dimensions, and prices. Every example must be marked as synthetic. Do not copy data from production systems, email, drawings, quotations, or licensed engineering publications.

## Engineering changes

Calculation changes must include applicability checks, explicit units, source responsibility, and regression tests. The repository must remain fail-closed when a required engineering property is missing.

--- 국문 번역 ---

# 기여 안내

## 개발

격리된 Python 환경을 만들고 개발 의존성을 설치한 뒤 변경 제출 전에 전체 테스트를 실행합니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
python scripts/verify_public_release.py .
```

## Fixture 정책

조직명, 식별자, 치수, 가격은 모두 가상 값으로 작성합니다. 모든 예시는 합성 데이터임을 표시해야 합니다. 생산 시스템, 메일, 도면, 견적, 라이선스가 필요한 엔지니어링 출판물의 데이터를 복사하지 마십시오.

## 엔지니어링 변경

계산 변경에는 적용 조건, 명시적 단위, 출처 책임, 회귀 테스트가 포함되어야 합니다. 필수 엔지니어링 물성치가 없으면 저장소는 반드시 fail-closed로 동작해야 합니다.
