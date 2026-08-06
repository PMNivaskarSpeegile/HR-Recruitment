# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class RoleMaster(models.Model):
    role_id = models.AutoField(primary_key=True)
    role_code = models.CharField(unique=True, max_length=10)
    role_name = models.CharField(unique=True, max_length=50)

    class Meta:
        managed = False
        db_table = 'role_master'
        
    def __str__(self):
        return self.role_name
    
class UserMaster(models.Model):
    user_id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=100)
    email = models.CharField(unique=True, max_length=150)
    mobile = models.CharField(max_length=15, blank=True, null=True)
    role = models.ForeignKey(RoleMaster, models.DO_NOTHING)
    is_active = models.BooleanField()
    username = models.CharField(unique=True, max_length=50)
    password_hash = models.TextField()
    created_by = models.ForeignKey('self', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('self', models.DO_NOTHING, db_column='updated_by', related_name='usermaster_updated_by_set', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'user_master'

    def __str__(self):
        return self.full_name

    # --- Minimal interface DRF/permissions expect from a logged-in user. ---
    # Our JWTAuthentication only ever attaches a UserMaster when a valid token
    # was presented, so an instance here always represents an authenticated user.
    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False
    
class ReqStatusMaster(models.Model):
    status_id = models.SmallAutoField(primary_key=True)
    status_name = models.CharField(unique=True, max_length=50)
    status_code = models.CharField(unique=True, max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='reqstatusmaster_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'req_status_master'

    def __str__(self):
        return self.status_name

class PriorityMaster(models.Model):
    priority_id = models.SmallAutoField(primary_key=True)
    priority_name = models.CharField(unique=True, max_length=30)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='prioritymaster_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'priority_master'

    def __str__(self):
        return self.priority_name

class NoticePeriodMaster(models.Model):
    np_id = models.SmallAutoField(primary_key=True)
    np_name = models.CharField(unique=True, max_length=30)
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='noticeperiodmaster_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'notice_period_master'

    def __str__(self):
        return self.np_name


class ReqTypeMaster(models.Model):
    req_type_id = models.SmallAutoField(primary_key=True)
    req_type_code = models.CharField(unique=True, max_length=50)
    req_type_name = models.CharField(max_length=60)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='reqtypemaster_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'req_type_master'

    def __str__(self):
        return self.req_type_name

class WorkModeMaster(models.Model):
    work_mode_id = models.SmallAutoField(primary_key=True)
    work_mode_code = models.CharField(unique=True, max_length=50)
    work_mode_name = models.CharField(max_length=30)
    is_active = models.BooleanField()
    created_by = models.ForeignKey(UserMaster, models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='workmodemaster_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'work_mode_master'

    def __str__(self):
        return self.work_mode_name
    
class SourceMaster(models.Model):
    source_id = models.SmallAutoField(primary_key=True)
    source_name = models.CharField(unique=True, max_length=60)
    source_type = models.CharField(max_length=40, blank=True, null=True)
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='sourcemaster_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'source_master'

    def __str__(self):
        return self.source_name
    
class ScreeningModeMaster(models.Model):
    """How a recruiter screening is conducted (Telephonic / Video).
    Replaces the misnamed interview_round_master."""
    screening_mode_id = models.SmallAutoField(primary_key=True)
    mode_name = models.CharField(unique=True, max_length=40)
    mode_code = models.CharField(unique=True, max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='screeningmodemaster_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'screening_mode_master'

    def __str__(self):
        return self.mode_name


class EmailTemplateMaster(models.Model):
    """Admin-editable email templates (e.g. the JD email). Body/subject use
    {placeholders} rendered at send/preview time."""
    template_id = models.SmallAutoField(primary_key=True)
    template_code = models.CharField(unique=True, max_length=40)
    name = models.CharField(max_length=80)
    subject = models.CharField(max_length=255)
    body = models.TextField()
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='emailtemplate_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'email_template_master'

    def __str__(self):
        return self.name


class RejectionReasonMaster(models.Model):
    """Structured reasons for negative outcomes (Not Suitable / Dropped /
    No Response / Rejected / Fake) — replaces free-text comments."""
    reason_id = models.SmallAutoField(primary_key=True)
    reason_name = models.CharField(unique=True, max_length=80)
    reason_code = models.CharField(unique=True, max_length=50, blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='rejectionreasonmaster_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'rejection_reason_master'

    def __str__(self):
        return self.reason_name
    
class LocationMaster(models.Model):
    location_id = models.AutoField(primary_key=True)
    city = models.CharField(max_length=60)
    state = models.CharField(max_length=60)
    country = models.CharField(max_length=60)
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='locationmaster_updated_by_set', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'location_master'
        unique_together = (('city', 'state', 'country'),)

    def __str__(self):
        return f"{self.city}, {self.state}"
    
class DomainMaster(models.Model):
    """Controlled classification data used only to organise Skills. Domains are
    never referenced directly by Candidates or Requirements — only Skills carry
    a domain_id FK to here, so renaming a domain reflects on every linked skill
    automatically."""
    domain_id = models.AutoField(primary_key=True)
    domain_name = models.CharField(unique=True, max_length=60)
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='domainmaster_updated_by_set', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'domain_master'

    def __str__(self):
        return self.domain_name


class CandidateStatusMaster(models.Model):
    """Global candidate disposition (New CV / Saved / Fake / Possible Duplicate /
    Blacklisted) — independent of any requirement. Split out from the mixed
    cv_status_master (see docs/POSITION_REDESIGN.md)."""
    candidate_status_id = models.SmallAutoField(primary_key=True)
    status_code = models.CharField(unique=True, max_length=50)
    status_name = models.CharField(max_length=60)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='candidatestatusmaster_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'candidate_status_master'

    def __str__(self):
        return self.status_name


class ApplicationStatusMaster(models.Model):
    """Per-(candidate, requirement) pipeline stage, owned by jd_cv_mapping. A
    candidate can be Rejected for one requirement and Shortlisted/Joined for
    another simultaneously."""
    application_status_id = models.SmallAutoField(primary_key=True)
    status_code = models.CharField(unique=True, max_length=50)
    status_name = models.CharField(max_length=60)
    description = models.TextField(blank=True, null=True)
    # Separates pipeline progression from dispositions: 'STAGE' | 'OUTCOME'.
    kind = models.CharField(max_length=10, blank=True, null=True)
    sort_order = models.SmallIntegerField(blank=True, null=True)
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='applicationstatusmaster_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'application_status_master'

    def __str__(self):
        return self.status_name


class PositionStatusMaster(models.Model):
    """Per-seat lifecycle (Open / In Progress / Closed / Cancelled / Hold)."""
    position_status_id = models.SmallAutoField(primary_key=True)
    status_code = models.CharField(unique=True, max_length=50)
    status_name = models.CharField(max_length=60)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='positionstatusmaster_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'position_status_master'

    def __str__(self):
        return self.status_name


class RequirementPosition(models.Model):
    """One hire-able seat within a requirement, with its own lifecycle. A seat is
    filled through the WINNING application (filled_by_mapping) on Join — candidates
    are never mapped directly to positions during the pipeline."""
    position_id = models.AutoField(primary_key=True)
    req = models.ForeignKey('RequirementTracker', models.DO_NOTHING, db_column='req_id')
    position_no = models.IntegerField()
    position_status = models.ForeignKey('PositionStatusMaster', models.DO_NOTHING, db_column='position_status_id', blank=True, null=True)
    filled_by_mapping = models.ForeignKey('JdCvMapping', models.DO_NOTHING, db_column='filled_by_mapping_id', blank=True, null=True)
    # WHY the seat is in its current status: NULL/'MANUAL' (human) vs
    # 'AUTO_REQ_HOLD'/'AUTO_REQ_CANCEL' (requirement cascade). Drives selective
    # auto-reopen (see requirements.positions). See core.constants.PositionSource.
    status_source = models.CharField(max_length=20, blank=True, null=True)
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='requirementposition_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'requirement_position'
        unique_together = (('req', 'position_no'),)

    def __str__(self):
        return f"{self.req_id}#{self.position_no}"


class SkillMaster(models.Model):
    skill_id = models.AutoField(primary_key=True)
    skill_name = models.CharField(unique=True, max_length=80)
    # Classification only — Skills remain the resume-facing master that
    # Candidates/Requirements reference; a Skill belongs to one Domain.
    domain = models.ForeignKey('DomainMaster', models.DO_NOTHING, db_column='domain_id', blank=True, null=True)
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='skillmaster_updated_by_set', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'skill_master'

    def __str__(self):
        return self.skill_name

class ClientMaster(models.Model):
    client_id = models.AutoField(primary_key=True)
    client_code = models.CharField(unique=True, max_length=50)
    client_name = models.CharField(max_length=120)
    industry = models.CharField(max_length=60, blank=True, null=True)
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='clientmaster_updated_by_set', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'client_master'

    def __str__(self):
        return self.client_name
    
class ClientManagerMaster(models.Model):
    client_mgr_id = models.AutoField(primary_key=True)
    client = models.ForeignKey('ClientMaster', models.DO_NOTHING)
    manager_name = models.CharField(max_length=100)
    designation = models.CharField(max_length=80, blank=True, null=True)
    email = models.CharField(max_length=150)
    mobile = models.CharField(max_length=15, blank=True, null=True)
    department = models.CharField(max_length=60, blank=True, null=True)
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='clientmanagermaster_updated_by_set', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'client_manager_master'
        unique_together = (('client', 'email'),)

    def __str__(self):
        return self.manager_name

class CandidateMaster(models.Model):
    cv_id = models.AutoField(primary_key=True)
    # Global candidate disposition (New CV / Saved / Fake / Possible Duplicate).
    candidate_status = models.ForeignKey('CandidateStatusMaster', models.DO_NOTHING, db_column='candidate_status_id', blank=True, null=True)
    cv_serial = models.CharField(unique=True, max_length=20)
    candidate_name = models.CharField(max_length=100)
    mobile = models.CharField(unique=True, max_length=15)
    email = models.CharField(unique=True, max_length=150)
    exp_min = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    exp_max = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    current_location = models.ForeignKey('LocationMaster', models.DO_NOTHING, blank=True, null=True)
    preferred_location = models.ForeignKey('LocationMaster', models.DO_NOTHING, related_name='candidatemaster_preferred_location_set', blank=True, null=True)
    notice_period = models.ForeignKey('NoticePeriodMaster', models.DO_NOTHING, blank=True, null=True)
    work_mode = models.ForeignKey('WorkModeMaster', models.DO_NOTHING, blank=True, null=True)
    current_company = models.CharField(max_length=100, blank=True, null=True)
    current_ctc_lpa = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    expected_ctc_lpa = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    highest_qualification = models.CharField(max_length=80, blank=True, null=True)
    source = models.ForeignKey('SourceMaster', models.DO_NOTHING, blank=True, null=True)
    is_duplicate = models.BooleanField()
    duplicate_of = models.ForeignKey(
        'self', models.DO_NOTHING, db_column='duplicate_of_cv_id',
        related_name='duplicates', blank=True, null=True,
    )
    is_willing_to_relocate = models.BooleanField()
    # Extra master-profile fields (verified during screening; see 0019).
    current_designation = models.CharField(max_length=120, blank=True, null=True)
    relevant_exp = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    certifications = models.TextField(blank=True, null=True)
    additional_notes = models.TextField(blank=True, null=True)
    # Bulk-import (Naukri template) preservation fields (see migration 0024).
    # age_at_import is the Excel snapshot — never recalculated; DOB is authoritative.
    date_of_birth = models.DateField(blank=True, null=True)
    age_at_import = models.SmallIntegerField(blank=True, null=True)
    postal_address = models.CharField(max_length=255, blank=True, null=True)
    # Original location text kept when it can't be mapped to location_master.
    current_location_text = models.CharField(max_length=150, blank=True, null=True)
    # The bulk-import batch that CREATED this candidate (NULL for manual creates
    # and for candidates only UPDATED by an import). See migration 0025.
    import_batch = models.ForeignKey('BulkImportBatch', models.DO_NOTHING, db_column='import_batch_id', blank=True, null=True)
    # Profile verification stamp (Verify & Update Profile).
    profile_verified = models.BooleanField(default=False)
    profile_verified_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='profile_verified_by', related_name='+', blank=True, null=True)
    profile_verified_on = models.DateTimeField(blank=True, null=True)
    # Candidate lifecycle automation (Reject-Hold / Joined). active_rejection_count
    # is a WORKING counter for automation only — never the historical record.
    active_rejection_count = models.IntegerField(default=0)
    reject_hold_start = models.DateField(blank=True, null=True)
    reject_hold_until = models.DateField(blank=True, null=True)
    joined_date = models.DateField(blank=True, null=True)
    last_status_changed_on = models.DateTimeField(blank=True, null=True)
    uploaded_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='uploaded_by')
    is_active = models.BooleanField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', related_name='candidatemaster_created_by_set', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='candidatemaster_updated_by_set', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'candidate_master'

    def __str__(self):
        return self.candidate_name


class BulkImportBatch(models.Model):
    """One bulk candidate upload — metadata, counts, and the per-row report.
    Created candidates point back here via candidate_master.import_batch_id
    (see migration 0025)."""
    batch_id = models.AutoField(primary_key=True)
    batch_uid = models.CharField(max_length=32, blank=True, null=True)
    uploaded_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='uploaded_by', blank=True, null=True)
    file_name = models.CharField(max_length=255, blank=True, null=True)
    file_hash = models.CharField(max_length=64, blank=True, null=True)
    source = models.ForeignKey('SourceMaster', models.DO_NOTHING, db_column='source_id', blank=True, null=True)
    requirement = models.ForeignKey('RequirementTracker', models.DO_NOTHING, db_column='requirement_id', blank=True, null=True)
    sheet_name = models.CharField(max_length=100, blank=True, null=True)
    header_row = models.SmallIntegerField(blank=True, null=True)
    total_rows = models.IntegerField(default=0)
    created_count = models.IntegerField(default=0)
    updated_count = models.IntegerField(default=0)
    duplicate_count = models.IntegerField(default=0)
    skipped_count = models.IntegerField(default=0)
    status = models.CharField(max_length=12, default='PENDING')  # PENDING/COMPLETED/FAILED/ROLLED_BACK
    row_report = models.JSONField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    completed_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'bulk_import_batch'


class RequirementTracker(models.Model):
    req_id = models.AutoField(primary_key=True)
    req_tracker_no = models.CharField(unique=True, max_length=20)
    jd_serial_number = models.CharField(unique=True, max_length=20, blank=True, null=True)
    client_req_id = models.CharField(max_length=50, blank=True, null=True)
    client = models.ForeignKey(ClientMaster, models.DO_NOTHING)
    client_mgr = models.ForeignKey(ClientManagerMaster, models.DO_NOTHING, blank=True, null=True)
    hiring_mgr = models.ForeignKey('UserMaster', models.DO_NOTHING, blank=True, null=True)
    recruiter = models.ForeignKey('UserMaster', models.DO_NOTHING, related_name='requirementtracker_recruiter_set', blank=True, null=True)
    req_type = models.ForeignKey(ReqTypeMaster, models.DO_NOTHING)
    jd_role_name = models.CharField(max_length=120)
    location = models.ForeignKey(LocationMaster, models.DO_NOTHING, blank=True, null=True)
    exp_min = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    exp_max = models.DecimalField(max_digits=4, decimal_places=1, blank=True, null=True)
    jd_rate_lpa = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    np = models.ForeignKey(NoticePeriodMaster, models.DO_NOTHING, blank=True, null=True)
    req_status = models.ForeignKey(ReqStatusMaster, models.DO_NOTHING)
    priority = models.ForeignKey(PriorityMaster, models.DO_NOTHING, blank=True, null=True)
    positions_open = models.SmallIntegerField()
    positions_filled = models.SmallIntegerField()
    skill1 = models.ForeignKey('SkillMaster', models.DO_NOTHING, blank=True, null=True)
    skill2 = models.ForeignKey('SkillMaster', models.DO_NOTHING, related_name='requirementtracker_skill2_set', blank=True, null=True)
    skill3 = models.ForeignKey('SkillMaster', models.DO_NOTHING, related_name='requirementtracker_skill3_set', blank=True, null=True)
    req_date = models.DateField()
    assigned_date = models.DateField(blank=True, null=True)
    target_fill_date = models.DateField(blank=True, null=True)
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', related_name='requirementtracker_created_by_set', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='requirementtracker_updated_by_set', blank=True, null=True)
    jd_text = models.TextField(blank=True, null=True)
    comments = models.TextField(blank=True, null=True)
    is_active = models.BooleanField()
    # Permanent "End Recruitment" business decision (an HM stops recruiting the
    # remaining seats of an expired, partially-filled requirement). This is the
    # source of truth for freezing the status rollup — see
    # requirements.positions.recompute_requirement — and for blocking recruitment;
    # the requirement status itself stays Partial Filled.
    recruitment_ended = models.BooleanField(default=False)
    recruitment_ended_on = models.DateTimeField(blank=True, null=True)
    recruitment_ended_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='recruitment_ended_by', related_name='requirementtracker_recruitment_ended_set', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'requirement_tracker'

    def __str__(self):
        return self.req_tracker_no


# ============================================================================
#  PHASE 1 — Pipeline & supporting tables
#  (See database/migrations/0001_phase1_pipeline.sql for the DDL.)
# ============================================================================

class CandidateSkill(models.Model):
    """Many-to-many link: a candidate has N skills. Powers skill tagging on
    upload (UC2) and global candidate search by skill (§9)."""
    cs_id = models.AutoField(primary_key=True)
    candidate = models.ForeignKey('CandidateMaster', models.DO_NOTHING, db_column='cv_id')
    skill = models.ForeignKey('SkillMaster', models.DO_NOTHING, db_column='skill_id')
    created_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'candidate_skill'
        unique_together = (('candidate', 'skill'),)

    def __str__(self):
        return f"{self.candidate_id}-{self.skill_id}"


class JdCvMapping(models.Model):
    """THE PIPELINE. Links a candidate to a requirement and tracks their
    per-requirement status through the screening workflow (UC3-UC5)."""
    mapping_id = models.AutoField(primary_key=True)
    req = models.ForeignKey('RequirementTracker', models.DO_NOTHING, db_column='req_id')
    candidate = models.ForeignKey('CandidateMaster', models.DO_NOTHING, db_column='cv_id')
    # Per-(candidate, requirement) pipeline STAGE and the SINGLE source of truth
    # for progress (Shortlisted → JD Sent → Screening → … → Joined; review
    # "Not Suitable" sets the NOT_SUITABLE stage). Distinct from
    # candidate_master.candidate_status (the candidate's global disposition).
    application_stage = models.ForeignKey('ApplicationStatusMaster', models.DO_NOTHING, db_column='application_stage_id', blank=True, null=True)
    # The last recorded disposition (kind=OUTCOME). Stage = where they are;
    # latest_outcome = the last thing that happened there. is_closed marks a
    # terminal (closing) outcome.
    latest_outcome = models.ForeignKey('ApplicationStatusMaster', models.DO_NOTHING, db_column='latest_outcome_id', related_name='mapping_outcome_set', blank=True, null=True)
    is_closed = models.BooleanField(default=False)
    closed_on = models.DateTimeField(blank=True, null=True)
    closed_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='closed_by', related_name='jdcvmapping_closed_set', blank=True, null=True)
    screening_mode = models.ForeignKey('ScreeningModeMaster', models.DO_NOTHING, db_column='screening_mode_id', blank=True, null=True)
    screening_datetime = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.ForeignKey('RejectionReasonMaster', models.DO_NOTHING, db_column='rejection_reason_id', blank=True, null=True)
    # The real date the candidate joined (set when application → JOINED).
    joined_date = models.DateField(blank=True, null=True)
    comments = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', related_name='jdcvmapping_created_set', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='jdcvmapping_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'jd_cv_mapping'
        unique_together = (('req', 'candidate'),)

    def __str__(self):
        return f"REQ {self.req_id} / CV {self.candidate_id}"


class CvDocument(models.Model):
    """Résumé file metadata. The actual file lives on disk (§8)."""
    document_id = models.AutoField(primary_key=True)
    candidate = models.ForeignKey('CandidateMaster', models.DO_NOTHING, db_column='cv_id')
    file_name = models.CharField(max_length=255)
    stored_file_name = models.CharField(max_length=255)
    file_path = models.TextField()
    file_type = models.CharField(max_length=20, blank=True, null=True)
    file_size = models.BigIntegerField(blank=True, null=True)
    active_version = models.BooleanField(default=True)
    upload_date = models.DateTimeField(blank=True, null=True)
    uploaded_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='uploaded_by', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'cv_document'

    def __str__(self):
        return self.file_name


class CandidateInteraction(models.Model):
    """Recruiter notes & interaction history (call notes, status-change
    remarks, duplicate resolution, etc.) — §10."""
    interaction_id = models.AutoField(primary_key=True)
    candidate = models.ForeignKey('CandidateMaster', models.DO_NOTHING, db_column='cv_id')
    req = models.ForeignKey('RequirementTracker', models.DO_NOTHING, db_column='req_id', blank=True, null=True)
    interaction_type = models.CharField(max_length=40)
    comment = models.TextField()
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'candidate_interaction'

    def __str__(self):
        return f"{self.interaction_type} on CV {self.candidate_id}"


class CommunicationLog(models.Model):
    """Record of every JD email (and future channels) sent to a candidate (§2)."""
    comm_id = models.AutoField(primary_key=True)
    candidate = models.ForeignKey('CandidateMaster', models.DO_NOTHING, db_column='cv_id')
    req = models.ForeignKey('RequirementTracker', models.DO_NOTHING, db_column='req_id', blank=True, null=True)
    channel = models.CharField(max_length=20, default='EMAIL')
    recipient = models.CharField(max_length=150)
    subject = models.CharField(max_length=255, blank=True, null=True)
    body = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, default='SENT')
    error_message = models.TextField(blank=True, null=True)
    sent_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='sent_by', blank=True, null=True)
    sent_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'communication_log'

    def __str__(self):
        return f"{self.channel} to {self.recipient}"


class Screening(models.Model):
    """One screening round of an application (jd_cv_mapping). Supports sequential
    rounds (Telephonic → Video → …); type comes from screening_mode_master
    (extensible). Status/outcome are fixed workflow enums (see core.constants)."""
    screening_id = models.BigAutoField(primary_key=True)
    mapping = models.ForeignKey('JdCvMapping', models.DO_NOTHING, db_column='mapping_id')
    screening_mode = models.ForeignKey('ScreeningModeMaster', models.DO_NOTHING, db_column='screening_mode_id')
    status = models.CharField(max_length=20, default='SCHEDULED')
    outcome = models.CharField(max_length=30, blank=True, null=True)
    scheduled_at = models.DateTimeField(blank=True, null=True)
    interviewer = models.CharField(max_length=150, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', related_name='screening_created_set', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='updated_by', related_name='screening_updated_set', blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'screening'

    def __str__(self):
        return f"Screening {self.screening_id} ({self.status})"


class ActivityLog(models.Model):
    """Cross-entity audit feed — one row per notable business event (requirement
    opened, candidate joined, requirement closed, …). Powers the Admin activity
    panel and future history/compliance views. Written best-effort by
    core.activity.log_activity (never blocks the business action)."""
    activity_id = models.BigAutoField(primary_key=True)
    activity_type = models.CharField(max_length=40)
    summary = models.TextField()
    req = models.ForeignKey('RequirementTracker', models.DO_NOTHING, db_column='req_id', blank=True, null=True)
    candidate = models.ForeignKey('CandidateMaster', models.DO_NOTHING, db_column='cv_id', blank=True, null=True)
    actor = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='actor_id', blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'activity_log'

    def __str__(self):
        return f"{self.activity_type}: {self.summary[:40]}"


class CandidateDuplicateReview(models.Model):
    """A detected possible-duplicate awaiting resolution — a SEPARATE process from
    the candidate lifecycle (never touches candidate_status). Stores the submitted
    (new) candidate details, the existing record it clashed with, why, and the
    full audit of who created/resolved it. Future merge hangs off this record."""
    review_id = models.AutoField(primary_key=True)
    existing_candidate = models.ForeignKey('CandidateMaster', models.DO_NOTHING, db_column='existing_cv_id')
    new_candidate_name = models.CharField(max_length=150)
    new_mobile = models.CharField(max_length=20)
    new_email = models.CharField(max_length=150, blank=True, null=True)
    submitted_payload = models.JSONField(blank=True, null=True)
    detection_reason = models.CharField(max_length=120)
    review_status = models.CharField(max_length=20, default='PENDING')  # PENDING | RESOLVED
    resolution = models.CharField(max_length=30, blank=True, null=True)  # MERGED | KEPT_SEPARATE | CORRECTED
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='created_by', blank=True, null=True, related_name='+')
    created_on = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='resolved_by', blank=True, null=True, related_name='+')
    resolved_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'candidate_duplicate_review'


class CandidateRequirementReview(models.Model):
    """PRE-PIPELINE association: a candidate explicitly put UNDER REVIEW for a
    requirement (the Review Pool). Created by tagging (manual create, bulk upload,
    or the profile "assign to requirement" action) — NOT by skill matching, and
    NOT the same as jd_cv_mapping (which means the candidate ENTERED the pipeline
    via Shortlist). One ACTIVE row per (candidate, requirement); a candidate may be
    under review for many requirements. Resolved when the recruiter decides
    (Shortlist/Talent Pool/Not Suitable/Fake/Blacklist), untags, or the
    requirement closes. History is preserved (status RESOLVED + resolution)."""
    review_id = models.AutoField(primary_key=True)
    candidate = models.ForeignKey('CandidateMaster', models.DO_NOTHING, db_column='cv_id')
    req = models.ForeignKey('RequirementTracker', models.DO_NOTHING, db_column='req_id')
    status = models.CharField(max_length=20, default='ACTIVE')      # ACTIVE | RESOLVED
    resolution = models.CharField(max_length=30, blank=True, null=True)  # ReviewResolution.*
    tagged_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='tagged_by', blank=True, null=True, related_name='+')
    tagged_on = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='resolved_by', blank=True, null=True, related_name='+')
    resolved_on = models.DateTimeField(blank=True, null=True)
    created_on = models.DateTimeField(blank=True, null=True)
    updated_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'candidate_requirement_review'
        unique_together = (('candidate', 'req'),)


class CandidateProfileAudit(models.Model):
    """Field-level audit of master-profile edits (one row per changed field).
    Append-only — history is never overwritten. Powers the candidate timeline
    detail and compliance/reporting."""
    audit_id = models.AutoField(primary_key=True)
    candidate = models.ForeignKey('CandidateMaster', models.DO_NOTHING, db_column='cv_id')
    field_name = models.CharField(max_length=60)
    old_value = models.TextField(blank=True, null=True)
    new_value = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=40, default='Recruiter Manual Update')
    changed_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='changed_by', related_name='+', blank=True, null=True)
    changed_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'candidate_profile_audit'


class StatusChangeHistory(models.Model):
    """Unified, append-only audit of requirement AND position status changes.
    Statuses are stored as CODES (not FKs) so the history stays immutable even
    if a master row changes. See core.constants.AuditEntity / ChangeType."""
    history_id = models.AutoField(primary_key=True)
    entity_type = models.CharField(max_length=20)      # 'REQUIREMENT' | 'POSITION'
    entity_id = models.IntegerField()
    previous_status = models.CharField(max_length=30, blank=True, null=True)
    new_status = models.CharField(max_length=30)
    reason = models.TextField(blank=True, null=True)
    change_type = models.CharField(max_length=10, default='MANUAL')  # 'MANUAL' | 'AUTO'
    changed_by = models.ForeignKey('UserMaster', models.DO_NOTHING, db_column='changed_by', related_name='+', blank=True, null=True)
    changed_on = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'status_change_history'
