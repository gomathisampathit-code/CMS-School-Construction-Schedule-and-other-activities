"""Forgot the password?  Run:  python reset_password.py
This removes the saved password. The next time you open the app it asks you to create a new one.
Your schedule, attendance and purchasing data are NOT touched."""
import db

db.init_db()
with db.conn() as c:
    c.execute("DELETE FROM settings WHERE key IN ('password_hash', 'fail_count', 'lock_until')")
print("Password removed. Start the app and create a new password.")
