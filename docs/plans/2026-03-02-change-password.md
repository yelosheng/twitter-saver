# Change Password Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an in-app password change feature accessible via a user dropdown menu in the navbar.

**Architecture:** Add a user dropdown to the navbar's right side (keeping the queue status indicator), a `/change-password` route in `app.py` using the existing `UserManager.change_password()` method, and a new `change_password.html` template.

**Tech Stack:** Flask, Jinja2, Bootstrap 5, existing `UserManager` (SHA-256 + salt, `users.json`)

---

### Task 1: Add user dropdown to navbar in `base.html`

**Files:**
- Modify: `templates/base.html:124-133`

**Step 1: Replace the status indicator block**

Find this block in `base.html` (lines 124–132):

```html
<div id="status-indicator" class="text-light">
    <small>
        <i id="queue-icon" class="bi bi-list-task"></i>
        <span id="queue-size">Queue: 0</span> |
        <i id="processing-icon" class="bi bi-pause-circle"></i>
        <span id="processing-status">Idle</span>
    </small>
</div>
```

Replace with:

```html
<div class="d-flex align-items-center gap-3">
    <div id="status-indicator" class="text-light">
        <small>
            <i id="queue-icon" class="bi bi-list-task"></i>
            <span id="queue-size">Queue: 0</span> |
            <i id="processing-icon" class="bi bi-pause-circle"></i>
            <span id="processing-status">Idle</span>
        </small>
    </div>
    <div class="dropdown">
        <a class="nav-link dropdown-toggle text-light" href="#" role="button" data-bs-toggle="dropdown">
            <i class="bi bi-person-circle"></i> {{ username }}
        </a>
        <ul class="dropdown-menu dropdown-menu-end">
            <li>
                <a class="dropdown-item" href="{{ url_for('change_password') }}">
                    <i class="bi bi-key"></i> Change Password
                </a>
            </li>
            <li><hr class="dropdown-divider"></li>
            <li>
                <a class="dropdown-item" href="{{ url_for('logout') }}">
                    <i class="bi bi-box-arrow-right"></i> Logout
                </a>
            </li>
        </ul>
    </div>
</div>
```

**Step 2: Verify template renders**

Start the server (`python run_web.py`) and confirm:
- Navbar shows `👤 admin ▾` on the right
- Clicking opens dropdown with "Change Password" and "Logout"
- Queue status still visible to the left of the dropdown

**Step 3: Commit**

```bash
git add templates/base.html
git commit -m "feat: add user dropdown with Change Password and Logout to navbar"
```

---

### Task 2: Create `templates/change_password.html`

**Files:**
- Create: `templates/change_password.html`

**Step 1: Create the template**

```html
{% extends "base.html" %}

{% block title %}Change Password - Twitter Saver{% endblock %}

{% block content %}
<div class="row">
    <div class="col-md-5 mx-auto">
        <h2 class="mb-4"><i class="bi bi-key"></i> Change Password</h2>

        {% if error %}
        <div class="alert alert-danger">{{ error }}</div>
        {% endif %}

        <div class="card">
            <div class="card-body">
                <form method="POST">
                    <div class="mb-3">
                        <label for="current_password" class="form-label">Current Password</label>
                        <input type="password" class="form-control" id="current_password"
                               name="current_password" required autofocus>
                    </div>
                    <div class="mb-3">
                        <label for="new_password" class="form-label">New Password</label>
                        <input type="password" class="form-control" id="new_password"
                               name="new_password" required>
                    </div>
                    <div class="mb-3">
                        <label for="confirm_password" class="form-label">Confirm New Password</label>
                        <input type="password" class="form-control" id="confirm_password"
                               name="confirm_password" required>
                    </div>
                    <div class="d-grid gap-2">
                        <button type="submit" class="btn btn-primary">
                            <i class="bi bi-check-lg"></i> Update Password
                        </button>
                        <a href="{{ url_for('index') }}" class="btn btn-outline-secondary">Cancel</a>
                    </div>
                </form>
            </div>
        </div>
    </div>
</div>
{% endblock %}
```

**Step 2: Commit**

```bash
git add templates/change_password.html
git commit -m "feat: add change_password template"
```

---

### Task 3: Add `/change-password` route to `app.py`

**Files:**
- Modify: `app.py` — insert after the `logout` route (after line 832)

**Step 1: Insert route**

After the `logout` route block (line 832, the line `return redirect(url_for('login'))`), insert:

```python
@app.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Change password page"""
    if request.method == 'POST':
        current_password = request.form.get('current_password', '')
        new_password = request.form.get('new_password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not current_password or not new_password or not confirm_password:
            return render_template('change_password.html', error='All fields are required')

        if new_password != confirm_password:
            return render_template('change_password.html', error='New passwords do not match')

        username = session.get('username')
        if user_manager.change_password(username, current_password, new_password):
            session.clear()
            return redirect(url_for('login'))
        else:
            return render_template('change_password.html', error='Current password is incorrect')

    return render_template('change_password.html')
```

**Step 2: Verify manually**

1. Start server: `python run_web.py`
2. Log in as `admin`
3. Click `👤 admin ▾` → "Change Password"
4. Enter wrong current password → should show error
5. Enter mismatched new passwords → should show error
6. Enter correct current password + matching new passwords → should redirect to login
7. Log in with the new password → should succeed
8. Change password back to `admin` for dev convenience

**Step 3: Commit**

```bash
git add app.py
git commit -m "feat: add /change-password route"
```

---

### Task 4: Push

```bash
git push
```
