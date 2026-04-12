from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models import Q
import uuid
from datetime import time, datetime, timedelta
from decimal import Decimal

class BaseModel(models.Model):
    """Abstract base model with common fields and audit trail"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        abstract = True
    
    def soft_delete(self):
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        self.is_deleted = False
        self.deleted_at = None
        self.save()

class AcademicYear(BaseModel):
    """Academic year management"""
    year = models.IntegerField(unique=True, validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    name = models.CharField(max_length=50)
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)
    is_open_for_registration = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-year']
        indexes = [
            models.Index(fields=['year', 'is_current']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        return f"{self.year} - {self.name}"
    
    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicYear.objects.filter(is_current=True).update(is_current=False)
        if self.start_date >= self.end_date:
            raise ValidationError("End date must be after start date")
        super().save(*args, **kwargs)
    
    @property
    def duration_days(self):
        return (self.end_date - self.start_date).days
    
    @property
    def is_active_now(self):
        today = timezone.now().date()
        return self.start_date <= today <= self.end_date

class Semester(BaseModel):
    """Semester management - 3 semesters per year"""
    SEMESTER_CHOICES = [
        ('JAN_APR', 'January - April (Spring)'),
        ('MAY_AUG', 'May - August (Summer)'),
        ('SEP_DEC', 'September - December (Fall)'),
    ]
    
    SEMESTER_NUMBERS = {
        'JAN_APR': 1,
        'MAY_AUG': 2,
        'SEP_DEC': 3,
    }
    
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, related_name='semesters')
    semester_type = models.CharField(max_length=10, choices=SEMESTER_CHOICES)
    name = models.CharField(max_length=100)
    semester_number = models.PositiveSmallIntegerField(editable=False)
    start_date = models.DateField()
    end_date = models.DateField()
    registration_deadline = models.DateField()
    add_drop_deadline = models.DateField()
    withdrawal_deadline = models.DateField()
    teaching_weeks = models.PositiveSmallIntegerField(default=14)
    exam_week_start = models.DateField(null=True, blank=True)
    exam_week_end = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=False)
    is_registration_open = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['academic_year', 'semester_type']
        ordering = ['academic_year', 'start_date']
        indexes = [
            models.Index(fields=['academic_year', 'is_active']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.pk and self.semester_type:
            self.semester_number = self.SEMESTER_NUMBERS.get(self.semester_type, 0)
    
    def __str__(self):
        return f"{self.academic_year.year} - {self.get_semester_type_display()}"
    
    def save(self, *args, **kwargs):
        if self.is_active:
            Semester.objects.filter(is_active=True).update(is_active=False)
        if self.start_date >= self.end_date:
            raise ValidationError("End date must be after start date")
        if self.registration_deadline > self.start_date:
            raise ValidationError("Registration deadline must be before or on start date")
        super().save(*args, **kwargs)
    
    @property
    def current_week(self):
        today = timezone.now().date()
        if today < self.start_date or today > self.end_date:
            return 0
        days_diff = (today - self.start_date).days
        week = (days_diff // 7) + 1
        return min(week, self.teaching_weeks)
    
    @property
    def weeks_remaining(self):
        return max(0, self.teaching_weeks - self.current_week)

class Department(BaseModel):
    """Academic department management"""
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True)
    hod_name = models.CharField(max_length=200, blank=True)
    hod_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    budget_code = models.CharField(max_length=50, blank=True)
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return f"{self.code} - {self.name}"

class Programme(BaseModel):
    """Certificate or Diploma programme management"""
    PROGRAMME_TYPES = [
        ('CERT', 'Certificate'),
        ('DIP', 'Diploma'),
        ('HDIP', 'Higher Diploma'),
    ]
    
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='programmes')
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20, unique=True)
    programme_type = models.CharField(max_length=4, choices=PROGRAMME_TYPES)
    duration_semesters = models.PositiveSmallIntegerField(default=4)
    duration_years = models.DecimalField(max_digits=3, decimal_places=1, default=2.0)
    minimum_credits = models.PositiveSmallIntegerField(default=60)
    maximum_credits = models.PositiveSmallIntegerField(default=72)
    description = models.TextField(blank=True)
    objectives = models.TextField(blank=True)
    entry_requirements = models.TextField(blank=True)
    
    class Meta:
        ordering = ['programme_type', 'code']
        indexes = [
            models.Index(fields=['code', 'programme_type']),
            models.Index(fields=['department', 'programme_type']),
        ]
    
    def __str__(self):
        return f"{self.get_programme_type_display()} - {self.name} ({self.code})"

class Stage(BaseModel):
    """Year/Semester stage of study"""
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name='stages')
    semester_number = models.PositiveSmallIntegerField()
    name = models.CharField(max_length=100)
    credits_required = models.PositiveSmallIntegerField(default=30)
    is_final_stage = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['programme', 'semester_number']
        unique_together = ['programme', 'semester_number']
        indexes = [
            models.Index(fields=['programme', 'semester_number']),
        ]
    
    def __str__(self):
        return f"{self.programme.code} - {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.name:
            self.name = f"Semester {self.semester_number}"
        super().save(*args, **kwargs)

class Unit(BaseModel):
    """Academic unit/subject with comprehensive details"""
    UNIT_TYPES = [
        ('CORE', 'Core Unit'),
        ('ELECTIVE', 'Elective'),
        ('PREREQUISITE', 'Prerequisite'),
        ('REQUIRED', 'Required'),
    ]
    
    ASSESSMENT_TYPES = [
        ('CAT', 'Continuous Assessment'),
        ('EXAM', 'Final Exam'),
        ('BOTH', 'Both CAT and Exam'),
        ('PRACTICAL', 'Practical Only'),
    ]
    
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=200)
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name='units')
    unit_type = models.CharField(max_length=12, choices=UNIT_TYPES, default='CORE')
    credit_hours = models.PositiveSmallIntegerField(default=3)
    lecture_hours_per_week = models.PositiveSmallIntegerField(default=2)
    tutorial_hours_per_week = models.PositiveSmallIntegerField(default=0)
    practical_hours_per_week = models.PositiveSmallIntegerField(default=0)
    total_hours_per_week = models.PositiveSmallIntegerField(editable=False, default=2)
    slots_per_week = models.PositiveSmallIntegerField(default=1)
    prerequisites = models.ManyToManyField('self', symmetrical=False, blank=True)
    corequisites = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='co_req_for')
    assessment_type = models.CharField(max_length=10, choices=ASSESSMENT_TYPES, default='BOTH')
    cat_weight = models.DecimalField(max_digits=5, decimal_places=2, default=30.00)
    exam_weight = models.DecimalField(max_digits=5, decimal_places=2, default=70.00)
    pass_mark = models.DecimalField(max_digits=5, decimal_places=2, default=50.00)
    description = models.TextField(blank=True)
    learning_outcomes = models.TextField(blank=True)
    syllabus = models.FileField(upload_to='syllabus/', blank=True, null=True)
    
    class Meta:
        ordering = ['code']
        indexes = [
            models.Index(fields=['code', 'name']),
            models.Index(fields=['stage', 'unit_type']),
        ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._original_lecture_hours = self.lecture_hours_per_week
        self._original_practical_hours = self.practical_hours_per_week
    
    def save(self, *args, **kwargs):
        # Auto-calculate total hours and slots
        self.total_hours_per_week = self.lecture_hours_per_week + self.tutorial_hours_per_week + self.practical_hours_per_week
        self.slots_per_week = max(1, (self.total_hours_per_week + 1) // 2)
        
        # Validate weights
        if self.assessment_type == 'BOTH' and (self.cat_weight + self.exam_weight) != 100:
            raise ValidationError("CAT and Exam weights must sum to 100")
        
        super().save(*args, **kwargs)
        
        # Clear cache if hours changed
        if (self._original_lecture_hours != self.lecture_hours_per_week or 
            self._original_practical_hours != self.practical_hours_per_week):
            from django.core.cache import cache
            cache.delete_pattern(f"timetable_*_{self.id}")
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    @property
    def has_prerequisites(self):
        return self.prerequisites.exists()
    
    @property
    def prerequisite_list(self):
        return list(self.prerequisites.values_list('code', flat=True))

class Intake(BaseModel):
    """Student cohort/group management"""
    name = models.CharField(max_length=100)
    programme = models.ForeignKey(Programme, on_delete=models.CASCADE, related_name='intakes')
    stage = models.ForeignKey(Stage, on_delete=models.CASCADE, related_name='intakes')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE)
    enrollment_date = models.DateField()
    student_count = models.PositiveIntegerField(default=0)
    male_count = models.PositiveIntegerField(default=0)
    female_count = models.PositiveIntegerField(default=0)
    expected_completion = models.DateField()
    units = models.ManyToManyField(Unit, through='IntakeUnit', related_name='intakes')
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-academic_year', 'programme']
        indexes = [
            models.Index(fields=['programme', 'stage', 'academic_year']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.programme.code} - {self.name}"
    
    def save(self, *args, **kwargs):
        if not self.name:
            self.name = f"{self.academic_year.year} {self.programme.code} Intake"
        super().save(*args, **kwargs)
    
    @property
    def gender_ratio(self):
        if self.student_count > 0:
            return {
                'male_percentage': (self.male_count / self.student_count) * 100,
                'female_percentage': (self.female_count / self.student_count) * 100
            }
        return {'male_percentage': 0, 'female_percentage': 0}

class IntakeUnit(BaseModel):
    """Units assigned to intake for a specific semester"""
    intake = models.ForeignKey(Intake, on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE)
    is_mandatory = models.BooleanField(default=True)
    is_elective_selected = models.BooleanField(default=False)
    exam_date = models.DateField(null=True, blank=True)
    exam_time = models.TimeField(null=True, blank=True)
    exam_venue = models.CharField(max_length=100, blank=True)
    room_assignment = models.ForeignKey('Room', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        unique_together = ['intake', 'unit', 'semester']
        ordering = ['intake', 'unit']
        indexes = [
            models.Index(fields=['intake', 'semester']),
            models.Index(fields=['unit', 'semester']),
        ]
    
    def __str__(self):
        return f"{self.intake} - {self.unit.code} ({self.semester.name})"

class Lecturer(BaseModel):
    """Teaching staff management with comprehensive details"""
    LECTURER_TYPES = [
        ('FT', 'Full-time'),
        ('PT', 'Part-time'),
        ('VS', 'Visiting'),
        ('CT', 'Contract'),
    ]
    
    TITLES = [
        ('PROF', 'Professor'),
        ('ASSOC', 'Associate Professor'),
        ('SR', 'Senior Lecturer'),
        ('LEC', 'Lecturer'),
        ('ASST', 'Assistant Lecturer'),
        ('TUT', 'Tutor'),
        ('DR', 'Dr.'),
        ('MR', 'Mr.'),
        ('MRS', 'Mrs.'),
        ('MS', 'Ms.'),
    ]
    
    QUALIFICATIONS = [
        ('PHD', 'PhD'),
        ('MASTERS', 'Masters'),
        ('BACHELORS', 'Bachelors'),
        ('DIPLOMA', 'Diploma'),
        ('CERTIFICATE', 'Certificate'),
    ]
    
    DAYS = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
    DAY_CHOICES = [(d, d.title()) for d in DAYS]
    
    staff_id = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=10, choices=TITLES, default='MR')
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    alternative_email = models.EmailField(blank=True)
    phone = models.CharField(max_length=15, blank=True)
    alternative_phone = models.CharField(max_length=15, blank=True)
    lecturer_type = models.CharField(max_length=2, choices=LECTURER_TYPES, default='FT')
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='lecturers')
    highest_qualification = models.CharField(max_length=15, choices=QUALIFICATIONS, default='MASTERS')
    specialization = models.CharField(max_length=200, blank=True)
    year_of_experience = models.PositiveSmallIntegerField(default=0)
    max_hours_per_week = models.PositiveSmallIntegerField(default=20, validators=[MinValueValidator(1), MaxValueValidator(40)])
    max_hours_per_day = models.PositiveSmallIntegerField(default=6, validators=[MinValueValidator(1), MaxValueValidator(8)])
    preferred_days = models.JSONField(default=list)  # For part-time: ["MON", "WED", "FRI"]
    preferred_time_slots = models.JSONField(default=list)  # ["SLOT_1", "SLOT_2"]
    unavailable_dates = models.JSONField(default=list)  # Specific dates unavailable
    unavailable_weeks = models.JSONField(default=list)  # Weeks unavailable
    qualified_units = models.ManyToManyField(Unit, related_name='qualified_lecturers', blank=True)
    profile_image = models.ImageField(upload_to='lecturers/', blank=True, null=True)
    bio = models.TextField(blank=True)
    research_interests = models.TextField(blank=True)
    publications_count = models.PositiveIntegerField(default=0)
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='lecturer_profile')
    is_available_for_supervision = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['staff_id']),
            models.Index(fields=['email']),
            models.Index(fields=['lecturer_type', 'department']),
            models.Index(fields=['is_active']),
        ]
    
    @property
    def full_name(self):
        if self.middle_name:
            return f"{self.get_title_display()} {self.first_name} {self.middle_name} {self.last_name}"
        return f"{self.get_title_display()} {self.first_name} {self.last_name}"
    
    @property
    def short_name(self):
        return f"{self.get_title_display()} {self.last_name}"
    
    def get_available_days(self):
        if self.lecturer_type == 'FT':
            return self.DAYS[:5]  # Monday to Friday
        return self.preferred_days
    
    def is_available_on(self, date, time_slot):
        """Check if lecturer is available on specific date and time"""
        # Check if date is in unavailable dates
        if str(date) in self.unavailable_dates:
            return False
        
        # Check if week is unavailable
        week_number = date.isocalendar()[1]
        if week_number in self.unavailable_weeks:
            return False
        
        # For part-time, check preferred days
        day_name = date.strftime('%a').upper()[:3]
        if self.lecturer_type != 'FT' and day_name not in self.preferred_days:
            return False
        
        # Check time slot preference
        if self.preferred_time_slots and time_slot not in self.preferred_time_slots:
            return False
        
        return True
    
    def get_current_workload(self, semester=None):
        """Calculate current teaching workload"""
        from django.db.models import Count
        if not semester:
            semester = Semester.objects.filter(is_active=True).first()
        
        if not semester:
            return 0
        
        return TimetableEntry.objects.filter(
            semester=semester,
            lecturer=self,
            status='PUBLISHED'
        ).count() * 2
    
    def get_remaining_hours(self, semester=None):
        """Calculate remaining available hours"""
        return max(0, self.max_hours_per_week - self.get_current_workload(semester))
    
    def __str__(self):
        return self.full_name

class Room(BaseModel):
    """Teaching venue management"""
    ROOM_TYPES = [
        ('LECTURE', 'Lecture Hall'),
        ('TUTORIAL', 'Tutorial Room'),
        ('LAB', 'Laboratory'),
        ('COMPUTER', 'Computer Lab'),
        ('CLINICAL', 'Clinical Lab'),
        ('SEMINAR', 'Seminar Room'),
        ('WORKSHOP', 'Workshop'),
    ]
    
    name = models.CharField(max_length=50)
    code = models.CharField(max_length=20, unique=True)
    room_type = models.CharField(max_length=10, choices=ROOM_TYPES)
    capacity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    building = models.CharField(max_length=100)
    floor = models.PositiveSmallIntegerField()
    has_projector = models.BooleanField(default=True)
    has_whiteboard = models.BooleanField(default=True)
    has_aircon = models.BooleanField(default=False)
    has_wifi = models.BooleanField(default=True)
    has_computers = models.BooleanField(default=False)
    number_of_computers = models.PositiveIntegerField(default=0)
    is_wheelchair_accessible = models.BooleanField(default=True)
    equipment = models.JSONField(default=list)
    maintenance_schedule = models.JSONField(default=list)  # Days when room is unavailable
    last_maintenance = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['building', 'floor', 'code']
        indexes = [
            models.Index(fields=['code']),
            models.Index(fields=['room_type', 'capacity']),
            models.Index(fields=['building']),
        ]
    
    def __str__(self):
        equipment_icons = []
        if self.has_projector:
            equipment_icons.append("📽️")
        if self.has_computers:
            equipment_icons.append("💻")
        if self.has_aircon:
            equipment_icons.append("❄️")
        
        equipment_str = " " + " ".join(equipment_icons) if equipment_icons else ""
        return f"{self.code} - {self.name} ({self.capacity} seats){equipment_str}"
    
    def is_available_on(self, date, time_slot):
        """Check if room is available on specific date and time"""
        day_name = date.strftime('%a').upper()[:3]
        
        # Check maintenance schedule
        if day_name in self.maintenance_schedule:
            return False
        
        # Check if already booked
        return not TimetableEntry.objects.filter(
            room=self,
            day=day_name,
            time_slot=time_slot,
            date=date,
            status='PUBLISHED'
        ).exists()
    
    @property
    def utilization_rate(self, semester=None):
        """Calculate room utilization rate"""
        if not semester:
            semester = Semester.objects.filter(is_active=True).first()
        
        if not semester:
            return 0
        
        total_slots = TimetableEntry.objects.filter(
            semester=semester,
            room=self,
            status='PUBLISHED'
        ).count()
        
        max_slots = 5 * 3 * semester.teaching_weeks  # 5 days * 3 slots * weeks
        return (total_slots / max_slots * 100) if max_slots > 0 else 0

class TimeSlot(models.Model):
    """Predefined time slots - 3 per day"""
    SLOT_CHOICES = [
        ('SLOT_1', '8:00 AM - 10:00 AM'),
        ('SLOT_2', '10:30 AM - 12:30 PM'),
        ('SLOT_3', '2:00 PM - 4:00 PM'),
        ('SLOT_4', '4:30 PM - 6:30 PM'),  # Evening slot for part-time
    ]
    
    slot_id = models.CharField(max_length=6, choices=SLOT_CHOICES, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    order = models.PositiveSmallIntegerField()
    is_evening = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return self.get_slot_id_display()
    
    def save(self, *args, **kwargs):
        if not self.order:
            self.order = {'SLOT_1': 1, 'SLOT_2': 2, 'SLOT_3': 3, 'SLOT_4': 4}.get(self.slot_id, 99)
        if self.slot_id == 'SLOT_4':
            self.is_evening = True
        super().save(*args, **kwargs)
    
    @property
    def duration_hours(self):
        delta = datetime.combine(timezone.now().date(), self.end_time) - datetime.combine(timezone.now().date(), self.start_time)
        return delta.seconds / 3600

class TimetableEntry(BaseModel):
    """Individual scheduled class with comprehensive tracking"""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending Approval'),
        ('PUBLISHED', 'Published'),
        ('CANCELLED', 'Cancelled'),
        ('RESCHEDULED', 'Rescheduled'),
        ('COMPLETED', 'Completed'),
        ('MISSED', 'Missed'),
    ]
    
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='timetable_entries')
    intake = models.ForeignKey(Intake, on_delete=models.CASCADE, related_name='timetable_entries')
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='timetable_entries')
    lecturer = models.ForeignKey(Lecturer, on_delete=models.CASCADE, related_name='timetable_entries')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='timetable_entries')
    day = models.CharField(max_length=3, choices=[('MON','Mon'), ('TUE','Tue'), ('WED','Wed'), ('THU','Thu'), ('FRI','Fri'), ('SAT','Sat')])
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    specific_date = models.DateField(null=True, blank=True)  # For specific date scheduling
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='DRAFT')
    week_number = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(16)])
    is_recurring = models.BooleanField(default=True)  # If False, this is a one-off class
    recurrence_pattern = models.JSONField(default=dict)  # For custom recurrence
    attendance_count = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    rescheduled_from = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='rescheduled_to')
    published_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_entries')
    approved_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['day', 'time_slot__order', 'week_number']
        indexes = [
            models.Index(fields=['semester', 'status']),
            models.Index(fields=['lecturer', 'day', 'time_slot', 'week_number']),
            models.Index(fields=['intake', 'day', 'time_slot', 'week_number']),
            models.Index(fields=['room', 'day', 'time_slot', 'week_number']),
            models.Index(fields=['specific_date']),
            models.Index(fields=['status', 'week_number']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['semester', 'lecturer', 'day', 'time_slot', 'week_number'],
                condition=Q(status='PUBLISHED'),
                name='unique_lecturer_per_week'
            ),
            models.UniqueConstraint(
                fields=['semester', 'intake', 'day', 'time_slot', 'week_number'],
                condition=Q(status='PUBLISHED'),
                name='unique_intake_per_week'
            ),
            models.UniqueConstraint(
                fields=['semester', 'room', 'day', 'time_slot', 'week_number'],
                condition=Q(status='PUBLISHED'),
                name='unique_room_per_week'
            ),
        ]
    
    def clean(self):
        """Validate business rules before saving"""
        # Validate specific date is within semester
        if self.specific_date:
            if self.specific_date < self.semester.start_date or self.specific_date > self.semester.end_date:
                raise ValidationError(f"Date {self.specific_date} is outside semester dates")
            
            # Check if day matches specific date
            expected_day = self.specific_date.strftime('%a').upper()[:3]
            if expected_day != self.day:
                raise ValidationError(f"Day {self.day} does not match the specific date ({expected_day})")
        
        # Validate lecturer availability for part-time
        if self.lecturer.lecturer_type in ['PT', 'VS', 'CT']:
            if self.day not in self.lecturer.get_available_days():
                raise ValidationError(f"Part-time lecturer not available on {self.get_day_display()}")
        
        # Validate lecturer max hours per day
        daily_hours = TimetableEntry.objects.filter(
            semester=self.semester,
            lecturer=self.lecturer,
            day=self.day,
            week_number=self.week_number,
            status__in=['PUBLISHED', 'PENDING']
        ).exclude(id=self.id).count() * 2
        
        if daily_hours + 2 > self.lecturer.max_hours_per_day:
            raise ValidationError(f"Lecturer exceeds daily limit of {self.lecturer.max_hours_per_day} hours")
        
        # Validate lecturer max hours per week
        weekly_hours = TimetableEntry.objects.filter(
            semester=self.semester,
            lecturer=self.lecturer,
            week_number=self.week_number,
            status__in=['PUBLISHED', 'PENDING']
        ).exclude(id=self.id).count() * 2
        
        if weekly_hours + 2 > self.lecturer.max_hours_per_week:
            raise ValidationError(f"Lecturer exceeds weekly limit of {self.lecturer.max_hours_per_week} hours")
        
        # Validate lecturer can teach this unit
        if not self.lecturer.qualified_units.filter(id=self.unit.id).exists():
            raise ValidationError(f"Lecturer {self.lecturer.short_name} is not qualified to teach {self.unit.name}")
        
        # Validate room capacity
        if self.intake.student_count > self.room.capacity:
            raise ValidationError(f"Room capacity ({self.room.capacity}) is less than intake size ({self.intake.student_count})")
        
        # Validate room type for practical units
        if self.unit.practical_hours_per_week > 0 and self.room.room_type not in ['LAB', 'CLINICAL', 'COMPUTER']:
            raise ValidationError("Practical units require a laboratory or specialized room")
        
        # Validate no duplicate within same day for intake (if same unit)
        duplicate_intake_unit = TimetableEntry.objects.filter(
            semester=self.semester,
            intake=self.intake,
            unit=self.unit,
            day=self.day,
            week_number=self.week_number,
            status__in=['PUBLISHED', 'PENDING']
        ).exclude(id=self.id).exists()
        
        if duplicate_intake_unit:
            raise ValidationError(f"Intake {self.intake.name} already has {self.unit.code} on {self.get_day_display()}")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        
        if self.status == 'PUBLISHED' and not self.published_at:
            self.published_at = timezone.now()
        
        if self.status == 'PUBLISHED' and not self.approved_at and self.approved_by:
            self.approved_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def cancel(self, reason, cancelled_by):
        """Cancel this timetable entry"""
        self.status = 'CANCELLED'
        self.cancellation_reason = reason
        self.save()
        
        # Create audit log
        ScheduleAudit.objects.create(
            timetable_entry=self,
            action='CANCELLED',
            old_value={'status': 'PUBLISHED'},
            new_value={'status': 'CANCELLED', 'reason': reason},
            changed_by=cancelled_by
        )
    
    def reschedule(self, new_day, new_time_slot, new_room, reason, rescheduled_by):
        """Reschedule this class"""
        old_values = {
            'day': self.day,
            'time_slot_id': str(self.time_slot_id),
            'room_id': str(self.room_id)
        }
        
        new_entry = TimetableEntry.objects.create(
            semester=self.semester,
            intake=self.intake,
            unit=self.unit,
            lecturer=self.lecturer,
            room=new_room,
            day=new_day,
            time_slot=new_time_slot,
            week_number=self.week_number,
            status='PENDING',
            rescheduled_from=self,
            notes=f"Rescheduled from original: {reason}"
        )
        
        self.status = 'RESCHEDULED'
        self.save()
        
        # Create audit log
        ScheduleAudit.objects.create(
            timetable_entry=self,
            action='RESCHEDULED',
            old_value=old_values,
            new_value={'day': new_day, 'time_slot_id': str(new_time_slot.id), 'room_id': str(new_room.id), 'reason': reason},
            changed_by=rescheduled_by
        )
        
        return new_entry
    
    def __str__(self):
        date_str = f" [Week {self.week_number}]"
        return f"{self.unit.code} - {self.day} {self.time_slot.slot_id}{date_str}"

class ConflictLog(BaseModel):
    """Log of scheduling conflicts with resolution tracking"""
    CONFLICT_TYPES = [
        ('LECTURER', 'Lecturer Conflict'),
        ('INTAKE', 'Intake Conflict'),
        ('ROOM', 'Room Conflict'),
        ('CAPACITY', 'Capacity Issue'),
        ('QUALIFICATION', 'Qualification Issue'),
        ('TIME', 'Time Constraint'),
        ('PREREQUISITE', 'Prerequisite Violation'),
    ]
    
    SEVERITY_LEVELS = [
        ('HIGH', 'High - Blocks scheduling'),
        ('MEDIUM', 'Medium - May cause issues'),
        ('LOW', 'Low - Informational only'),
    ]
    
    RESOLUTION_STATUS = [
        ('PENDING', 'Pending'),
        ('AUTO_RESOLVED', 'Auto-resolved by AI'),
        ('MANUAL', 'Manually Resolved'),
        ('OVERRIDDEN', 'Overridden'),
        ('IGNORED', 'Ignored'),
    ]
    
    conflict_type = models.CharField(max_length=15, choices=CONFLICT_TYPES)
    severity = models.CharField(max_length=6, choices=SEVERITY_LEVELS, default='MEDIUM')
    description = models.TextField()
    involved_entities = models.JSONField()  # Store IDs of involved objects
    proposed_solution = models.JSONField(null=True, blank=True)
    resolution_status = models.CharField(max_length=13, choices=RESOLUTION_STATUS, default='PENDING')
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_conflicts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='conflicts')
    affected_entry = models.ForeignKey(TimetableEntry, on_delete=models.SET_NULL, null=True, blank=True, related_name='conflicts')
    
    class Meta:
        ordering = ['-created_at', '-severity']
        indexes = [
            models.Index(fields=['semester', 'resolution_status']),
            models.Index(fields=['conflict_type', 'severity']),
        ]
    
    def __str__(self):
        return f"{self.get_conflict_type_display()} - {self.created_at.date()} [{self.get_severity_display()}]"
    
    def resolve(self, resolution, resolved_by, resolution_method='MANUAL'):
        """Resolve this conflict"""
        self.proposed_solution = resolution
        self.resolution_status = resolution_method
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        self.save()

class ScheduleAudit(BaseModel):
    """Comprehensive audit log for all timetable changes"""
    ACTION_CHOICES = [
        ('CREATE', 'Created'),
        ('UPDATE', 'Updated'),
        ('DELETE', 'Deleted'),
        ('PUBLISH', 'Published'),
        ('UNPUBLISH', 'Unpublished'),
        ('MOVE', 'Moved'),
        ('CANCEL', 'Cancelled'),
        ('RESCHEDULE', 'Rescheduled'),
        ('BULK_UPDATE', 'Bulk Update'),
        ('APPROVE', 'Approved'),
        ('REJECT', 'Rejected'),
    ]
    
    timetable_entry = models.ForeignKey(TimetableEntry, on_delete=models.CASCADE, related_name='audits')
    action = models.CharField(max_length=12, choices=ACTION_CHOICES)
    old_value = models.JSONField(null=True, blank=True)
    new_value = models.JSONField(null=True, blank=True)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='timetable_audits')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    reason = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = "Schedule Audits"
        indexes = [
            models.Index(fields=['timetable_entry', 'action']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_action_display()} - {self.timetable_entry} at {self.created_at}"

class LecturerPreferences(BaseModel):
    """Lecturer preferences for scheduling"""
    lecturer = models.ForeignKey(Lecturer, on_delete=models.CASCADE, related_name='preferences')
    semester = models.ForeignKey(Semester, on_delete=models.CASCADE, related_name='lecturer_preferences')
    preferred_days = models.JSONField(default=list)
    preferred_time_slots = models.JSONField(default=list)
    blocked_days = models.JSONField(default=list)
    blocked_time_slots = models.JSONField(default=list)
    max_consecutive_hours = models.PositiveSmallIntegerField(default=4)
    prefer_morning = models.BooleanField(default=False)
    prefer_afternoon = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = ['lecturer', 'semester']
        verbose_name_plural = "Lecturer Preferences"
    
    def __str__(self):
        return f"Preferences for {self.lecturer.full_name} - {self.semester.name}"