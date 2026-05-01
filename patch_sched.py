c=open('timetable/scheduler.py','r',encoding='utf-8').read()
fixes=[]
old1 = '''    def _write(
        self,
        cohort:   Cohort,
        unit:     CurriculumUnit,
        trainer:  Trainer,
        room:     Room,
        day:      str,
        period:   Period,
        sequence: int,
    ) -> ScheduledUnit:
        entry, _ = ScheduledUnit.objects.update_or_create(
            term=self.term,
            cohort=cohort,
            curriculum_unit=unit,
            period=period,
            defaults={
'''
