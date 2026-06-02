from models.db import query


class Application:

    @staticmethod
    def create(user_id, job_title, company, job_url='', location='',
               salary='', match_score=0, source='manual', resume_id=None):
        app_id = query(
            """INSERT INTO applications
               (user_id, resume_id, job_title, company, job_url,
                location, salary, match_score, source, status)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'pending')""",
            (user_id, resume_id, job_title, company, job_url,
             location, salary, match_score, source),
            commit=True
        )
        return app_id

    @staticmethod
    def update_status(app_id, status):
        query(
            "UPDATE applications SET status = %s WHERE id = %s",
            (status, app_id), commit=True
        )

    @staticmethod
    def get_by_user(user_id, limit=50):
        return query(
            """SELECT * FROM applications
               WHERE user_id = %s
               ORDER BY applied_at DESC LIMIT %s""",
            (user_id, limit), fetchall=True
        )

    @staticmethod
    def get_stats(user_id):
        row = query(
            """SELECT
                COUNT(*) AS total,
                SUM(status = 'applied')   AS applied,
                SUM(status = 'viewed')    AS viewed,
                SUM(status = 'interview') AS interviews,
                SUM(status = 'rejected')  AS rejected
               FROM applications WHERE user_id = %s""",
            (user_id,), fetchone=True
        )
        return row or {}

    @staticmethod
    def already_applied(user_id, job_url):
        row = query(
            "SELECT id FROM applications WHERE user_id=%s AND job_url=%s",
            (user_id, job_url), fetchone=True
        )
        return row is not None