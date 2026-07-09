# Oreate Register URL Context Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 Oreate 注册链路从 `register_url` 解析并透传真实注册页 query 上下文，修复 `emailsignupin`/`emailregisterconfirm` 参数漂移导致的注册失败。

**Architecture:** 在注册配置层新增 `register_url`，在 `oreate_register.py` 内集中解析 URL query，产出稳定的 register context，并由 `OreateRegistrar` 在请求链路中统一复用。邀请号池仍保留现有行为，但会覆盖 URL 里的 `inviteCode`，避免双源冲突。

**Tech Stack:** FastAPI, Pydantic, curl_cffi, Vue 3, TypeScript, unittest

## Global Constraints

- 不回退现有用户改动
- 只做注册链路相关最小修复
- 生产代码前必须先有失败测试
- 声称修复前必须跑新鲜验证

---

### Task 1: Add failing tests for register URL context

**Files:**
- Create: `unit_tests/test_oreate_register_context.py`
- Test: `unit_tests/test_oreate_register_context.py`

**Interfaces:**
- Consumes: `services.register.oreate_register.OreateRegistrar`
- Produces: regression tests for register URL parsing and payload construction

- [ ] **Step 1: Write the failing test**

```python
def test_register_context_uses_query_values():
    registrar = oreate_register.OreateRegistrar(
        proxy="",
        register_url="https://www.oreateai.com/userlogin/register?fr=inviteFriend&inviteCode=abc&fissionCode=xyz",
    )
    assert registrar.register_context["fr"] == "inviteFriend"
    assert registrar.register_context["invite_code"] == "abc"
    assert registrar.register_context["fission_code"] == "xyz"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest unit_tests/test_oreate_register_context.py -v`
Expected: FAIL because `register_url` / `register_context` do not exist yet

- [ ] **Step 3: Write minimal implementation**

```python
def _resolve_register_context(...):
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest unit_tests/test_oreate_register_context.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add unit_tests/test_oreate_register_context.py services/register/oreate_register.py
git commit -m "fix: derive oreate register context from url"
```

### Task 2: Wire register_url through config and API

**Files:**
- Modify: `services/register/oreate_register.py`
- Modify: `services/register_service.py`
- Modify: `api/register.py`
- Modify: `web-vue/src/api/register.ts`

**Interfaces:**
- Consumes: persisted `register.json` config
- Produces: `register_url` available in backend and frontend config payloads

- [ ] **Step 1: Write the failing test**

```python
def test_signup_uses_register_url_as_referer():
    ...
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest unit_tests/test_oreate_register_context.py -v`
Expected: FAIL because requests still use hard-coded register referer

- [ ] **Step 3: Write minimal implementation**

```python
class RegisterConfigRequest(BaseModel):
    register_url: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest unit_tests/test_oreate_register_context.py unit_tests/test_oreate_register_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/register_service.py api/register.py web-vue/src/api/register.ts services/register/oreate_register.py unit_tests/test_oreate_register_context.py
git commit -m "fix: plumb oreate register url config"
```

### Task 3: Expose register_url in the register UI and refresh docs

**Files:**
- Modify: `web-vue/src/views/Register.vue`
- Modify: `DEPLOY_OREATE.md`

**Interfaces:**
- Consumes: frontend register config model
- Produces: editable register URL field and updated protocol notes

- [ ] **Step 1: Write the failing test**

```text
Manual verification target: register page config cannot edit register_url
```

- [ ] **Step 2: Run test to verify it fails**

Run: `rg -n "register_url" web-vue/src/views/Register.vue DEPLOY_OREATE.md`
Expected: no UI field, no updated docs

- [ ] **Step 3: Write minimal implementation**

```vue
<Input v-model.trim="registerConfig.register_url" ... />
```

- [ ] **Step 4: Run test to verify it passes**

Run: `rg -n "register_url|fissionCode|jt" web-vue/src/views/Register.vue DEPLOY_OREATE.md`
Expected: field and docs present

- [ ] **Step 5: Commit**

```bash
git add web-vue/src/views/Register.vue DEPLOY_OREATE.md
git commit -m "docs: surface oreate register url context"
```
