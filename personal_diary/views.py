import calendar, json, os
from datetime import date, timedelta
from io import BytesIO
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.core.paginator import Paginator
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from . import drive_storage
from .access import diary_access_required
from .forms import DiaryEntryForm, ImportantEventForm
from .models import DiaryAccessSettings, DiaryEntry, DiaryMedia, DiaryPreference, ImportantEvent

def _entries_for(r): return DiaryEntry.objects.filter(user=r.user, deleted_at__isnull=True).prefetch_related('tags')
def _owned_entry(r, pk): return get_object_or_404(_entries_for(r), pk=pk)
def _preference(u): return DiaryPreference.objects.get_or_create(user=u)[0]
def _ensure_locked_entry_pin(entry):
    """Create the user-requested date PIN only when no diary PIN exists yet."""
    if not entry.is_locked:
        return False
    preference = _preference(entry.user)
    if preference.pin_hash:
        return False
    preference.pin_hash = make_password(entry.entry_date.strftime('%d%m%Y'))
    preference.save(update_fields=('pin_hash', 'updated_at'))
    return True
def _unlocked(r, e): return not e.is_locked or r.session.get('diary_unlock_until', 0) >= int(timezone.now().timestamp())
def _require_unlocked(r, e):
    if not _unlocked(r, e): raise Http404
def _private(response): response['Cache-Control'] = 'private, no-store'; return response

@diary_access_required
@never_cache
def dashboard(request):
    today = timezone.localdate(); entries = _entries_for(request); preference = _preference(request.user)
    published_entries = entries.filter(is_draft=False)
    on_day = entries.filter(entry_date__month=today.month, entry_date__day=today.day, entry_date__year__lt=today.year)
    events = ImportantEvent.objects.filter(user=request.user, event_date__month=today.month, event_date__day=today.day, event_date__year__lt=today.year)
    stats = entries.filter(entry_date__year=today.year, entry_date__month=today.month).values('mood').annotate(total=Count('id')).order_by('mood')
    return render(request, 'personal_diary/dashboard.html', {'today': today, 'today_entries': published_entries.filter(entry_date=today), 'recent_entries': published_entries[:6], 'favorite_entries': published_entries.filter(is_favorite=True)[:4], 'entry_count': published_entries.count(), 'mood_stats': stats, 'on_this_day_entries': on_day if preference.on_this_day_enabled else [], 'on_this_day_events': events if preference.on_this_day_enabled else [], 'on_this_day_enabled': preference.on_this_day_enabled})

@diary_access_required
@never_cache
def entry_list(request):
    # Autosave drafts are recovery copies, not separate diary entries.  Keep them
    # out of the normal "My entries" history so an interrupted compose session
    # cannot look like duplicate published entries.
    entries = _entries_for(request).filter(is_draft=False); query, mood, category = (request.GET.get(k, '').strip() for k in ('q','mood','category'))
    if query: entries = entries.filter(Q(title__icontains=query)|Q(content__icontains=query)|Q(tags__name__icontains=query)).distinct()
    if mood in DiaryEntry.Mood.values: entries = entries.filter(mood=mood)
    if category in DiaryEntry.Category.values: entries = entries.filter(category=category)
    entry_date = request.GET.get('date', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    # Invalid date values are ignored deliberately; the list remains usable.
    def valid_date(value):
        try:
            date.fromisoformat(value)
            return value
        except ValueError:
            return ''
    entry_date, date_from, date_to = map(valid_date, (entry_date, date_from, date_to))
    if entry_date: entries = entries.filter(entry_date=entry_date)
    if date_from: entries = entries.filter(entry_date__gte=date_from)
    if date_to: entries = entries.filter(entry_date__lte=date_to)
    if request.GET.get('favorite') == '1': entries = entries.filter(is_favorite=True)
    sort = request.GET.get('sort', 'newest')
    entries = entries.order_by('entry_date', 'entry_time', 'id') if sort == 'oldest' else entries.order_by('-entry_date', '-entry_time', '-id')
    paginator = Paginator(entries, 30)
    page_obj = paginator.get_page(request.GET.get('page'))
    query_params = request.GET.copy()
    query_params.pop('page', None)
    return render(request, 'personal_diary/entry_list.html', {'entries': page_obj, 'page_obj': page_obj, 'query_string': query_params.urlencode(), 'query':query, 'mood':mood, 'category':category, 'entry_date':entry_date, 'date_from':date_from, 'date_to':date_to, 'sort':sort, 'moods':DiaryEntry.Mood, 'categories':DiaryEntry.Category})

@diary_access_required
@never_cache
def entry_create(request):
    form = DiaryEntryForm(request.POST or None, user=request.user, initial={'entry_date':request.GET.get('date')} if request.GET.get('date') else None)
    if request.method == 'POST' and form.is_valid():
        entry=form.save(commit=False); entry.user=request.user; entry.save(); entry.tags.set([request.user.diary_tags.get_or_create(name=x)[0] for x in form.cleaned_data['tags_text']]);
        if _ensure_locked_entry_pin(entry): messages.info(request, 'Private entry PIN has been set to its date in DDMMYYYY format. Change it from Diary PIN settings.')
        messages.success(request, 'Diary entry saved.'); return redirect('personal_diary:entry_detail', pk=entry.pk)
    return render(request, 'personal_diary/entry_form.html', {'form':form, 'page_title':'नई डायरी लिखें'})

@diary_access_required
@never_cache
def entry_detail(request, pk):
    entry=_owned_entry(request,pk)
    # Covers older private entries created before the date-PIN default existed.
    _ensure_locked_entry_pin(entry)
    if entry.is_locked and not _unlocked(request,entry): return render(request,'personal_diary/unlock.html',{'entry':entry,'has_pin':bool(_preference(request.user).pin_hash)})
    return _private(render(request,'personal_diary/entry_detail.html',{'entry':entry,'media_items':entry.media.filter(deleted_at__isnull=True)}))

@diary_access_required
@never_cache
def entry_update(request,pk):
    entry=_owned_entry(request,pk); _require_unlocked(request,entry); form=DiaryEntryForm(request.POST or None,instance=entry,user=request.user)
    if request.method=='POST' and form.is_valid():
        entry = form.save()
        if _ensure_locked_entry_pin(entry): messages.info(request, 'Private entry PIN has been set to its date in DDMMYYYY format. Change it from Diary PIN settings.')
        messages.success(request, 'Diary entry updated.'); return redirect('personal_diary:entry_detail',pk=entry.pk)
    return render(request,'personal_diary/entry_form.html',{'form':form,'entry':entry,'page_title':'डायरी बदलें'})

@diary_access_required
@require_POST
def entry_delete(request,pk):
    entry=_owned_entry(request,pk); _require_unlocked(request,entry); entry.soft_delete(); messages.success(request, 'Diary entry moved to recycle bin.'); return redirect('personal_diary:entry_list')

@diary_access_required
@never_cache
def calendar_view(request):
    today=timezone.localdate()
    try: year,month=int(request.GET.get('year',today.year)),int(request.GET.get('month',today.month))
    except ValueError: raise Http404
    if not 1<=month<=12 or not 2000<=year<=2100: raise Http404
    data=_entries_for(request).filter(entry_date__year=year,entry_date__month=month).values('entry_date').annotate(total=Count('id'))
    counts={x['entry_date'].day:x['total'] for x in data}; weeks=[[(d,counts.get(d.day,0) if d.month==month else 0) for d in w] for w in calendar.Calendar().monthdatescalendar(year,month)]
    return render(request,'personal_diary/calendar.html',{'year':year,'month':month,'month_name':calendar.month_name[month],'weeks':weeks,'counts':counts,'previous_month':date(year-1,12,1) if month==1 else date(year,month-1,1),'next_month':date(year+1,1,1) if month==12 else date(year,month+1,1)})

def _media_spec(f):
    ext=os.path.splitext(f.name)[1].lower(); head=f.read(32); f.seek(0)
    specs={'.jpg':('PHOTO','image/jpeg',lambda x:x.startswith(b'\xff\xd8\xff')),'.jpeg':('PHOTO','image/jpeg',lambda x:x.startswith(b'\xff\xd8\xff')),'.png':('PHOTO','image/png',lambda x:x.startswith(b'\x89PNG\r\n\x1a\n')),'.webp':('PHOTO','image/webp',lambda x:x[:4]==b'RIFF' and x[8:12]==b'WEBP'),'.mp4':('VIDEO','video/mp4',lambda x:x[4:8]==b'ftyp'),'.mov':('VIDEO','video/quicktime',lambda x:x[4:8]==b'ftyp'),'.webm':('VIDEO','video/webm',lambda x:x.startswith(b'\x1aE\xdf\xa3')),'.mp3':('AUDIO','audio/mpeg',lambda x:x.startswith(b'ID3') or x[:2]==b'\xff\xfb'),'.m4a':('AUDIO','audio/mp4',lambda x:x[4:8]==b'ftyp'),'.wav':('AUDIO','audio/wav',lambda x:x[:4]==b'RIFF' and x[8:12]==b'WAVE')}; s=specs.get(ext)
    return s[:2] if s and s[2](head) and (not f.content_type or f.content_type in {s[1],'application/octet-stream'}) else None

@diary_access_required
@require_POST
def media_upload(request,pk):
    entry=_owned_entry(request,pk); _require_unlocked(request,entry); files=request.FILES.getlist('files')
    if not files or len(files)>int(getattr(settings,'PERSONAL_DIARY_MAX_ATTACHMENTS',20)): return HttpResponse('Invalid attachment count.',status=400)
    specs=[(f,_media_spec(f)) for f in files]
    if any(not s for _,s in specs): return HttpResponse('Unsupported or invalid media file.',status=400)
    ids=[]
    try:
      with transaction.atomic():
        limits=DiaryAccessSettings.objects.select_for_update().get(user=request.user); used=DiaryMedia.objects.filter(user=request.user,deleted_at__isnull=True).aggregate(total=Sum('file_size'))['total'] or 0; quota=limits.storage_quota_bytes or settings.PERSONAL_DIARY_USER_QUOTA_BYTES
        if used+sum(f.size for f,_ in specs)>quota: return HttpResponse('Storage quota exceeded.',status=400)
        for f,(kind,mime) in specs:
          max_size=getattr(limits,{'PHOTO':'photo_max_upload_bytes','VIDEO':'video_max_upload_bytes','AUDIO':'audio_max_upload_bytes'}[kind]) or getattr(settings,'PERSONAL_DIARY_%s_MAX_BYTES'%kind)
          if f.size>max_size:return HttpResponse('Media size limit exceeded.',status=400)
        for f,(kind,mime) in specs:
          result,parent,name=drive_storage.upload(f,request.user.pk,kind,mime); ids.append(result['id']); DiaryMedia.objects.create(user=request.user,entry=entry,drive_file_id=result['id'],drive_parent_folder_id=parent,original_filename=name,media_type=kind,mime_type=mime,file_size=f.size)
    except Exception:
      for file_id in ids: drive_storage.delete(file_id)
      return HttpResponse('Media could not be uploaded.',status=503)
    return redirect('personal_diary:entry_detail',pk=entry.pk)

@diary_access_required
@never_cache
def media_download(request,pk):
    media=get_object_or_404(DiaryMedia,pk=pk,user=request.user,deleted_at__isnull=True,entry__deleted_at__isnull=True); _require_unlocked(request,media.entry)
    return _private(FileResponse(drive_storage.download(media.drive_file_id),as_attachment=request.GET.get('download')=='1',filename=media.original_filename,content_type=media.mime_type))
@diary_access_required
@require_POST
def media_delete(request,pk):
    media=get_object_or_404(DiaryMedia,pk=pk,user=request.user,deleted_at__isnull=True); _require_unlocked(request,media.entry); media.soft_delete(); messages.success(request, 'Media removed from gallery.'); return redirect('personal_diary:gallery')
@diary_access_required
@never_cache
def gallery(request):
    items=DiaryMedia.objects.filter(user=request.user,deleted_at__isnull=True,entry__deleted_at__isnull=True).select_related('entry'); typ=request.GET.get('type')
    if typ in DiaryMedia.MediaType.values: items=items.filter(media_type=typ)
    if request.GET.get('date'):items=items.filter(uploaded_at__date=request.GET['date'])
    return _private(render(request,'personal_diary/gallery.html',{'items':[x for x in items if _unlocked(request,x.entry)],'types':DiaryMedia.MediaType,'selected_type':typ or ''}))

@diary_access_required
@never_cache
def event_list(request): return render(request,'personal_diary/event_list.html',{'events':ImportantEvent.objects.filter(user=request.user)})
@diary_access_required
@never_cache
def event_form(request,pk=None):
    event=get_object_or_404(ImportantEvent,pk=pk,user=request.user) if pk else None; form=ImportantEventForm(request.POST or None,instance=event)
    if request.method=='POST' and form.is_valid(): obj=form.save(commit=False); obj.user=request.user; obj.save(); messages.success(request, 'Event saved.'); return redirect('personal_diary:event_list')
    return render(request,'personal_diary/event_form.html',{'form':form,'event':event})
@diary_access_required
@require_POST
def event_delete(request,pk): get_object_or_404(ImportantEvent,pk=pk,user=request.user).delete(); messages.success(request, 'Event deleted.'); return redirect('personal_diary:event_list')

@diary_access_required
@require_POST
def autosave(request,pk=None):
    try: data=json.loads(request.body or '{}')
    except ValueError:return JsonResponse({'error':'invalid_json'},status=400)
    is_new_draft = pk is None
    entry=_owned_entry(request,pk) if pk else DiaryEntry(user=request.user,is_draft=True)
    if data.get('updated_at') and entry.pk and data['updated_at']!=entry.updated_at.isoformat():return JsonResponse({'error':'conflict','updated_at':entry.updated_at.isoformat()},status=409)
    # Autosave must never turn an already published entry back into a draft.
    entry.title=str(data.get('title',entry.title or 'Untitled'))[:180]; entry.content=str(data.get('content',entry.content))
    if is_new_draft:
        entry.is_draft=True
    if data.get('mood') in DiaryEntry.Mood.values:entry.mood=data['mood']
    entry.save(); return JsonResponse({'id':entry.pk,'updated_at':entry.updated_at.isoformat(), 'autosave_url': reverse('personal_diary:autosave', args=[entry.pk]), 'edit_url': reverse('personal_diary:entry_update', args=[entry.pk])})

@diary_access_required
@require_POST
def unlock_entry(request,pk):
    entry=_owned_entry(request,pk); pref=_preference(request.user)
    if not pref.pin_hash or not check_password(request.POST.get('pin',''),pref.pin_hash):
        return render(request, 'personal_diary/unlock.html', {
            'entry': entry,
            'has_pin': bool(pref.pin_hash),
            'error': 'PIN is incorrect. Please try again.',
        }, status=403)
    request.session['diary_unlock_until']=int((timezone.now()+timedelta(minutes=15)).timestamp()); return redirect('personal_diary:entry_detail',pk=entry.pk)
@diary_access_required
@never_cache
def pin_settings(request):
    pref=_preference(request.user)
    if request.method=='POST':
      if pref.pin_hash and not check_password(request.POST.get('current_pin',''),pref.pin_hash):return render(request,'personal_diary/pin.html',{'error':'Current PIN is incorrect.','has_pin':True})
      pin=request.POST.get('new_pin','')
      if not pin.isdigit() or not 4<=len(pin)<=12:return render(request,'personal_diary/pin.html',{'error':'PIN must be 4–12 digits.','has_pin':bool(pref.pin_hash)})
      pref.pin_hash=make_password(pin);pref.save(update_fields=('pin_hash','updated_at'));return redirect('personal_diary:dashboard')
    return render(request,'personal_diary/pin.html',{'has_pin':bool(pref.pin_hash)})
@diary_access_required
@require_POST
def pin_reset(request):
    if request.POST.get('confirmation')!='RESET':return HttpResponse('Confirmation required.',status=400)
    pref=_preference(request.user);pref.pin_hash='';pref.save(update_fields=('pin_hash','updated_at'));request.session.pop('diary_unlock_until',None);return redirect('personal_diary:pin_settings')
@diary_access_required
@require_POST
def on_this_day_preference(request):
    pref=_preference(request.user);pref.on_this_day_enabled=request.POST.get('enabled')=='1';pref.save(update_fields=('on_this_day_enabled','updated_at'));return redirect('personal_diary:dashboard')

def _export_entries(request):
    q=_entries_for(request)
    if request.GET.get('from'):q=q.filter(entry_date__gte=request.GET['from'])
    if request.GET.get('to'):q=q.filter(entry_date__lte=request.GET['to'])
    return [x for x in q if _unlocked(request,x)]
@diary_access_required
@never_cache
def export_json(request):
    entries=_export_entries(request);data=[{'date':x.entry_date.isoformat(),'time':x.entry_time.isoformat(),'title':x.title,'content':x.content,'mood':x.mood,'category':x.category,'favorite':x.is_favorite,'locked':x.is_locked,'tags':list(x.tags.values_list('name',flat=True))} for x in entries]
    response=JsonResponse({'entries':data,'events':list(ImportantEvent.objects.filter(user=request.user).values('title','event_date','event_type','note'))},json_dumps_params={'ensure_ascii':False});response['Content-Disposition']='attachment; filename="my-diary.json"';return _private(response)
@diary_access_required
@never_cache
def export_pdf(request):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph,SimpleDocTemplate,Spacer
    path=getattr(settings,'PERSONAL_DIARY_PDF_FONT_PATH','')
    if not path or not os.path.exists(path):return HttpResponse('Diary PDF font is not configured.',status=503)
    pdfmetrics.registerFont(TTFont('DiaryUnicode',path));out=BytesIO(); styles=getSampleStyleSheet();styles['BodyText'].fontName=styles['Heading1'].fontName='DiaryUnicode';story=[Paragraph('मेरी डायरी',styles['Heading1'])]
    for x in _export_entries(request):story += [Paragraph(f'{x.entry_date} — {x.title}',styles['Heading2']),Paragraph(x.content.replace('\n','<br/>'),styles['BodyText']),Spacer(1,12)]
    SimpleDocTemplate(out,pagesize=A4).build(story);out.seek(0);return _private(FileResponse(out,as_attachment=True,filename='my-diary.pdf',content_type='application/pdf'))
