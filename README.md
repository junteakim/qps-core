# QPS Core

QPS Core is a public, data-agnostic pressure vessel quotation framework. It demonstrates explicit engineering inputs, configurable cost lines, formula-first Excel review, and RDF with SHACL validation.

## Public scope

- Internal pressure calculation functions that require caller-supplied material properties
- Configurable quotation arithmetic with mandatory cost provenance
- Formula-first Excel review workbook with a structural formula contract
- RDF projection and SHACL validation for quotation snapshots
- A static dashboard that uses synthetic records only
- Automated tests and a public release security gate

## Safety boundary

This repository contains no customer records, emails, production prices, commercial margins, licensed codebook tables, or private infrastructure settings. All bundled identifiers and values are synthetic.

The engineering functions do not select allowable stress or establish code compliance. Users must provide licensed, edition-specific material properties and complete an independent engineering review.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
qps-core demo --output demo-output
```

The demo creates:

- `demo-output/review_workbook.xlsx`
- `demo-output/final_snapshot.json`
- `demo-output/engineering_demo.json`

Open the synthetic dashboard:

```bash
python -m http.server 8000 -d web
```

Then visit `http://localhost:8000`.

## License status

No reuse license has been granted for this repository. Public visibility permits inspection, but it does not grant rights to copy, modify, or distribute the source. See `NOTICE.md`.

--- 국문 번역 ---

# QPS Core

QPS Core는 데이터와 분리된 공개 압력용기 견적 프레임워크입니다. 명시적 엔지니어링 입력, 설정형 원가 항목, formula-first Excel 검토, RDF와 SHACL 검증 구조를 보여줍니다.

## 공개 범위

- 사용자가 재질 물성치를 직접 제공하는 내압 계산 함수
- 원가 근거가 필수인 설정형 견적 산술
- 구조적 수식 계약을 갖는 formula-first Excel 검토 파일
- 견적 스냅샷의 RDF 변환과 SHACL 검증
- 합성 레코드만 사용하는 정적 대시보드
- 자동 테스트와 공개 릴리스 보안 게이트

## 안전 경계

이 저장소에는 고객 기록, 메일, 실제 단가, 영업 마진, 라이선스가 필요한 코드북 표, 사설 인프라 설정이 없습니다. 포함된 식별자와 수치는 모두 합성 데이터입니다.

엔지니어링 함수는 허용응력을 선택하거나 코드 적합성을 확정하지 않습니다. 사용자는 정식 라이선스와 해당 판본에 맞는 재질 물성치를 제공하고 독립적인 엔지니어링 검토를 완료해야 합니다.

## 빠른 시작

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
pytest
qps-core demo --output demo-output
```

데모는 다음 파일을 생성합니다.

- `demo-output/review_workbook.xlsx`
- `demo-output/final_snapshot.json`
- `demo-output/engineering_demo.json`

합성 대시보드는 다음 명령으로 엽니다.

```bash
python -m http.server 8000 -d web
```

이후 `http://localhost:8000`에 접속합니다.

## 라이선스 상태

이 저장소에는 재사용 라이선스가 부여되지 않았습니다. 공개 상태는 열람만 허용하며 소스 복사, 수정, 배포 권리를 부여하지 않습니다. 자세한 내용은 `NOTICE.md`를 확인하십시오.
