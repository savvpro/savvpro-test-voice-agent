# Git Bash everywhere on Windows (this machine)

Git is installed at:

```text
D:\Softwares\Git
```

Goal: open **Git Bash** from Start search, and get **Git Bash Here** when you right-click a folder.

## 1) Put Git on your User PATH

1. Press **Win**, type **environment variables**, open **Edit the system environment variables**.
2. Click **Environment Variables…**
3. Under **User variables**, select **Path** → **Edit** → **New**, add both:

```text
D:\Softwares\Git\cmd
D:\Softwares\Git\bin
```

4. OK out of all dialogs.
5. **Close and reopen** any PowerShell / CMD / terminal windows (PATH only refreshes for new sessions).

### One-liner (PowerShell — current user PATH)

Run once in PowerShell:

```powershell
[Environment]::SetEnvironmentVariable(
  "Path",
  [Environment]::GetEnvironmentVariable("Path", "User") + ";D:\Softwares\Git\cmd;D:\Softwares\Git\bin",
  "User"
)
```

Then open a **new** PowerShell window and check:

```powershell
git --version
bash --version
where.exe git
```

You should see something like `git version 2.x…` and a path under `D:\Softwares\Git\…`.

## 2) “Git Bash Here” on right-click

### Easiest: re-run the Git installer

1. Run the Git for Windows installer again (same version is fine).
2. When you reach **Windows Explorer integration**, tick:
   - **Git Bash Here**
   - (optional) **Git GUI Here**
3. Finish the installer. No need to reinstall the whole toolchain if it offers “Modify”.

After that, right-click a folder (or empty space inside a folder) → **Git Bash Here**.

### If you use Windows 11 modern context menu

Right-click → **Show more options** → then **Git Bash Here** often appears on the classic menu.

### Registry notes (only if installer option is missing)

Git’s installer normally writes keys under:

- `HKEY_CLASSES_ROOT\Directory\shell\git_shell`
- `HKEY_CLASSES_ROOT\Directory\Background\shell\git_shell`

Prefer the installer over hand-editing the registry. If those keys are missing, re-run the installer with Explorer integration enabled.

## 3) Open Git Bash from Start search

1. Press **Win**.
2. Type **Git Bash**.
3. Open **Git Bash** (mintty). Working directory is usually your user profile; `cd` into your project:

```bash
cd /c/Users/CodeTech/Desktop/savvpro-test-voice-agent-SUBMIT
```

## 4) Verify

In Git Bash:

```bash
git --version
bash --version
which git
pwd
```

In a new PowerShell:

```powershell
git --version
bash --version
```

## 5) Common snags

| Problem | Fix |
| --- | --- |
| `git` not recognized | PATH not updated; reopen terminal; confirm `D:\Softwares\Git\cmd` is on User Path |
| Right-click missing Git Bash | Re-run installer → Explorer integration; on Win11 use **Show more options** |
| Wrong Git picked up | `where.exe git` — remove older Git folders from PATH if another install shadows this one |
| Line endings weird on Windows | For this take-home, `git config --global core.autocrlf true` is usually fine |

You do **not** need admin rights for the User PATH one-liner. System PATH changes need admin; User PATH is enough.
