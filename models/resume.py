from models.db import query
import json


class Resume:

    @staticmethod
    def create(user_id, filename, stored_path, raw_text, skills,
               job_title='', industry='', job_description=''):
        skills_json = json.dumps(skills) if isinstance(skills, list) else skills
        resume_id = query(
            """INSERT INTO resumes
               (user_id, filename, stored_path, raw_text, skills_extracted,
                job_title, industry, job_description)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (user_id, filename, stored_path, raw_text, skills_json,
             job_title, industry, job_description),
            commit=True
        )
        return resume_id

    @staticmethod
    def get_by_id(resume_id):
        return query("SELECT * FROM resumes WHERE id = %s", (resume_id,), fetchone=True)

    @staticmethod
    def get_by_user(user_id, limit=10):
        return query(
            "SELECT * FROM resumes WHERE user_id = %s ORDER BY upload_date DESC LIMIT %s",
            (user_id, limit), fetchall=True
        )

    @staticmethod
    def get_latest(user_id):
        return query(
            "SELECT * FROM resumes WHERE user_id = %s ORDER BY upload_date DESC LIMIT 1",
            (user_id,), fetchone=True
        )