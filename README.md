# QPS Core

QPS Core is a public, domain-neutral workflow kernel for sequential stages, explicit gates, and local artifact tracking. The core contains no pricing or engineering policy. A pressure vessel quotation workflow is included as a reference adapter.

## Public scope

- Domain-neutral orchestration for caller-defined Python stages
- Explicit `PASS` or `HOLD` outcomes with gate evidence
- Output-directory confinement for registered artifacts
- Internal pressure calculation functions that require caller-supplied material properties
- Configurable quotation arithmetic with mandatory cost provenance
- Formula-first Excel review workbook with a structural formula contract
- RDF projection and SHACL validation for quotation snapshots
- Fail-closed caller-signoff gate
- Artifact provenance hashes and a machine-readable pipeline receipt
- A static dashboard that uses synthetic records only
- Automated tests and a public release security gate

## Safety boundary

This repository contains no customer records, emails, production prices, commercial margins, licensed codebook tables, or private infrastructure settings. All bundled identifiers and values are synthetic.

The engineering functions do not select allowable stress or establish code compliance. Users must provide licensed, edition-specific material properties and complete an independent engineering review.

Production pricing policies, customer-specific rules, private benchmarks, and internal workflow extensions are outside this repository. The pressure vessel reference adapter accepts caller-supplied values but does not contain the private policy layer that produces them.

The generic kernel does not load plugins dynamically or execute shell commands. Stage handlers are direct Python callables supplied by the embedding application. They run with the host process permissions and must be trusted application code. The kernel is not a sandbox for untrusted plugins. The pressure vessel adapter records a caller-asserted signoff but does not authenticate or authorize the reviewer. Production integrations must enforce reviewer identity and permission before constructing a signoff.

## Generic kernel

Create stages as direct callables, then compose them with `WorkflowKernel`. Each stage receives a `WorkflowContext` that carries the input payload, shared in-memory values, output directory, gates, and registered artifacts.

```python
from qps_core import StageOutcome, WorkflowContext, WorkflowKernel, WorkflowStage

def validate(context: WorkflowContext) -> StageOutcome:
    passed = bool(context.payload.get("records"))
    context.record_gate("records_present", passed, "checked input records")
    return StageOutcome("PASS" if passed else "HOLD", "records_present")

kernel = WorkflowKernel(
    "record_review",
    (WorkflowStage("validate", validate),),
)
result = kernel.run({"records": [{"id": "example"}]}, "generic-output")
print(result.to_dict())
```

Run the bundled domain-neutral example:

```bash
python examples/generic_workflow.py --output generic-output
```

The kernel is intentionally small. Domain adapters own their input schemas, calculations, authorization, and receipt contracts.

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
- `demo-output/normalized_request.json`
- `demo-output/pipeline_receipt.json`

The default run stays on `HOLD` because no signoff is present. A reviewer can record an explicit caller-asserted synthetic signoff for the run. This changes the workflow status to `CALLER_SIGNED_OFF`, not to an authenticated production approval.

```bash
qps-core demo \
  --output demo-output \
  --signoff-by SYNTHETIC_REVIEWER \
  --signoff-reference SYNTHETIC_SIGNOFF_001
```

Open the synthetic dashboard:

```bash
python -m http.server 8000 -d web
```

Then visit `http://localhost:8000`.

## License status

No reuse license has been granted for this repository. Public visibility permits inspection, but it does not grant rights to copy, modify, or distribute the source. See `NOTICE.md`.

--- 국문 번역 ---

# QPS Core

QPS Core는 순차 단계, 명시적 게이트, 로컬 산출물 추적을 위한 공개 범용 워크플로우 커널입니다. 코어에는 가격이나 엔지니어링 정책이 없습니다. 압력용기 견적 워크플로우는 참조 어댑터로 포함됩니다.

## 공개 범위

- 호출자가 정의한 Python 단계를 위한 범용 오케스트레이션
- 게이트 근거를 포함한 명시적 `PASS` 또는 `HOLD` 결과
- 등록 산출물의 출력 디렉터리 내부 제한
- 사용자가 재질 물성치를 직접 제공하는 내압 계산 함수
- 원가 근거가 필수인 설정형 견적 산술
- 구조적 수식 계약을 갖는 formula-first Excel 검토 파일
- 견적 스냅샷의 RDF 변환과 SHACL 검증
- fail-closed 호출자 signoff 게이트
- 산출물 provenance 해시와 기계 판독형 pipeline receipt
- 합성 레코드만 사용하는 정적 대시보드
- 자동 테스트와 공개 릴리스 보안 게이트

## 안전 경계

이 저장소에는 고객 기록, 메일, 실제 단가, 영업 마진, 라이선스가 필요한 코드북 표, 사설 인프라 설정이 없습니다. 포함된 식별자와 수치는 모두 합성 데이터입니다.

엔지니어링 함수는 허용응력을 선택하거나 코드 적합성을 확정하지 않습니다. 사용자는 정식 라이선스와 해당 판본에 맞는 재질 물성치를 제공하고 독립적인 엔지니어링 검토를 완료해야 합니다.

실제 가격 정책, 고객별 규칙, 비공개 벤치마크, 내부 워크플로우 확장은 이 저장소 범위 밖입니다. 압력용기 참조 어댑터는 사용자가 제공한 값을 받을 수 있지만 그 값을 만드는 비공개 정책 계층은 포함하지 않습니다.

범용 커널은 플러그인을 동적으로 불러오거나 셸 명령을 실행하지 않습니다. 단계 핸들러는 연동 애플리케이션이 직접 제공하는 Python 호출 객체입니다. 핸들러는 호스트 프로세스 권한으로 실행되므로 신뢰할 수 있는 애플리케이션 코드여야 합니다. 이 커널은 신뢰할 수 없는 플러그인을 격리하는 샌드박스가 아닙니다. 압력용기 어댑터는 호출자가 주장한 signoff를 기록하지만 검토자 신원을 인증하거나 권한을 확인하지 않습니다. 실제 연동 계층은 signoff를 만들기 전에 검토자 신원과 권한을 검증해야 합니다.

## 범용 커널

단계를 직접 호출 가능한 함수로 만든 뒤 `WorkflowKernel`로 조합합니다. 각 단계는 입력 payload, 공유 메모리 값, 출력 디렉터리, 게이트, 등록 산출물을 담는 `WorkflowContext`를 받습니다.

```python
from qps_core import StageOutcome, WorkflowContext, WorkflowKernel, WorkflowStage

def validate(context: WorkflowContext) -> StageOutcome:
    passed = bool(context.payload.get("records"))
    context.record_gate("records_present", passed, "checked input records")
    return StageOutcome("PASS" if passed else "HOLD", "records_present")

kernel = WorkflowKernel(
    "record_review",
    (WorkflowStage("validate", validate),),
)
result = kernel.run({"records": [{"id": "example"}]}, "generic-output")
print(result.to_dict())
```

포함된 범용 예제는 다음과 같이 실행합니다.

```bash
python examples/generic_workflow.py --output generic-output
```

커널은 의도적으로 작게 유지됩니다. 도메인 어댑터가 입력 스키마, 계산, 권한 확인, receipt 계약을 소유합니다.

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
- `demo-output/normalized_request.json`
- `demo-output/pipeline_receipt.json`

기본 실행은 signoff가 없으므로 `HOLD` 상태를 유지합니다. 검토자는 다음과 같이 호출자 주장 방식의 합성 signoff를 기록할 수 있습니다. 이때 상태는 인증된 운영 승인이 아니라 `CALLER_SIGNED_OFF`로 바뀝니다.

```bash
qps-core demo \
  --output demo-output \
  --signoff-by SYNTHETIC_REVIEWER \
  --signoff-reference SYNTHETIC_SIGNOFF_001
```

합성 대시보드는 다음 명령으로 엽니다.

```bash
python -m http.server 8000 -d web
```

이후 `http://localhost:8000`에 접속합니다.

## 라이선스 상태

이 저장소에는 재사용 라이선스가 부여되지 않았습니다. 공개 상태는 열람만 허용하며 소스 복사, 수정, 배포 권리를 부여하지 않습니다. 자세한 내용은 `NOTICE.md`를 확인하십시오.
