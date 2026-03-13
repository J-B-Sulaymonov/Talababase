from .base import *

@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    change_list_template = "admin/kadrlar/department_change_list.html"
    list_display = ('colored_name', 'head_manager_col', 'styled_employee_count','order')
    list_display_links = ('colored_name',)
    search_fields = ('name',)
    list_editable = ('order',)
    ordering = ('order',)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if is_hr_admin(request.user) or is_edu_admin(request.user):
            return qs
        return qs.filter(head_manager=request.user)

    def has_change_permission(self, request, obj=None):
        if is_hr_admin(request.user):
            return True
        if obj and obj.head_manager == request.user:
            return True
        return False

    def get_readonly_fields(self, request, obj=None):
        if not is_hr_admin(request.user):
            return ('name', 'slug', 'head_manager', 'created_by')
        return ()

    def colored_name(self, obj):
        return format_html(
            '''<div style="display: flex; align-items: center;">
                <span style="display: inline-flex; align-items: center; justify-content: center; 
                    width: 35px; height: 35px; background: #eef2f7; border-radius: 8px; 
                    margin-right: 12px; color: #3b82f6;">
                    <i class="fas fa-building"></i>
                </span>
                <span style="font-size: 15px; font-weight: 600; color: #334155;">{}</span>
            </div>''', obj.name
        )

    colored_name.short_description = "Kafedra / Bo'lim"

    def head_manager_col(self, obj):
        if obj.head_manager:
            return format_html('<i class="fas fa-user-tie" style="color:#64748b"></i> {}',
                               obj.head_manager.get_full_name() or obj.head_manager.username)
        return format_html('<span style="color:#ef4444">Tayinlanmagan</span>')

    head_manager_col.short_description = "Rahbar"

    def styled_employee_count(self, obj):
        count = Employee.objects.filter(Q(department=obj) | Q(department2=obj), archived=False).count()
        if count == 0:
            url = reverse("admin:kadrlar_employee_changelist")
            query = urlencode({'department__id': obj.id})
            style = "background-color: #fff1f2; color: #e11d48; padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: bold; box-shadow: 0 4px 6px -1px rgba(16, 185, 129, 0.4); text-decoration: none;"
            return format_html('<a href="{}?{}" style="{}">{} <i class="fas fa-arrow-right"></i></a>', url, query,
                               style,
                               f"Xodimlar yo'q")
        url = reverse("admin:kadrlar_employee_changelist")
        query = urlencode({'department__id': obj.id})
        style = "background: linear-gradient(135deg, #10b981 0%, #059669 100%); color: white; padding: 6px 14px; border-radius: 20px; font-size: 12px; font-weight: bold; box-shadow: 0 4px 6px -1px rgba(16, 185, 129, 0.4); text-decoration: none;"
        return format_html('<a href="{}?{}" style="{}">{} <i class="fas fa-arrow-right"></i></a>', url, query, style,
                           f"{count} nafar")

    styled_employee_count.short_description = "Xodimlar Soni"


    def changelist_view(self, request, extra_context=None):
        response = super().changelist_view(request, extra_context=extra_context)
        if hasattr(response, 'context_data'):
            try:
                cl = response.context_data['cl']
                qs = cl.queryset

                # Arxivlanmagan barcha xodimlarni olamiz (ushbu filtrlangan kafedralar bo'yicha)
                all_employees = Employee.objects.filter(Q(department__in=qs) | Q(department2__in=qs), archived=False).distinct()

                stats = {
                    'total_depts': qs.count(),

                    # Jami xodimlar (arxivsiz)
                    'total_employees': all_employees.count(),

                    # Faol xodimlar (Active statusda va arxivsiz)
                    'active_employees': all_employees.filter(status='active').count(),

                    # Kutilayotganlar
                    'pending_employees': all_employees.filter(status='pending').count(),
                }
                response.context_data['stats'] = stats
            except (KeyError, AttributeError):
                pass
        return response


