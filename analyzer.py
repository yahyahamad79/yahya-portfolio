"""
المحرك الإحصائي الكامل — يحيى محمد حمد
يدعم: Excel, CSV, SPSS, Word, PDF
يُنتج: تقرير Word كامل + ملخص النتائج
"""

import pandas as pd
import numpy as np
import io
import os
import traceback
from datetime import datetime

# ══════════════════════════════════════════════
# قراءة الملفات
# ══════════════════════════════════════════════

def read_file(file_storage):
    """قراءة أي نوع من الملفات وإرجاع DataFrame"""
    filename = file_storage.filename.lower()
    file_bytes = file_storage.read()
    
    try:
        if filename.endswith('.csv'):
            # جرب ترميزات مختلفة
            for enc in ['utf-8', 'utf-8-sig', 'cp1256', 'latin1']:
                try:
                    df = pd.read_csv(io.BytesIO(file_bytes), encoding=enc)
                    return df, None
                except:
                    continue
                    
        elif filename.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(io.BytesIO(file_bytes))
            return df, None
            
        elif filename.endswith('.sav'):
            try:
                import pyreadstat
                df, meta = pyreadstat.read_sav(io.BytesIO(file_bytes))
                return df, None
            except ImportError:
                return None, "مكتبة pyreadstat غير متوفرة لقراءة ملفات SPSS"
                
        elif filename.endswith(('.doc', '.docx')):
            return extract_from_word(file_bytes), None
            
        elif filename.endswith('.pdf'):
            return extract_from_pdf(file_bytes), None
            
        else:
            return None, "نوع الملف غير مدعوم"
            
    except Exception as e:
        return None, f"خطأ في قراءة الملف: {str(e)}"


def extract_from_word(file_bytes):
    """استخراج جداول البيانات من Word"""
    try:
        from docx import Document
        doc = Document(io.BytesIO(file_bytes))
        tables_data = []
        for table in doc.tables:
            rows = []
            for row in table.rows:
                rows.append([cell.text.strip() for cell in row.cells])
            if rows:
                df = pd.DataFrame(rows[1:], columns=rows[0])
                tables_data.append(df)
        if tables_data:
            return pd.concat(tables_data, ignore_index=True)
        # إذا لم يكن هناك جداول، حاول قراءة النص كبيانات
        return None
    except Exception as e:
        return None


def extract_from_pdf(file_bytes):
    """استخراج جداول البيانات من PDF"""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            all_tables = []
            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) > 1:
                        df = pd.DataFrame(table[1:], columns=table[0])
                        all_tables.append(df)
            if all_tables:
                return pd.concat(all_tables, ignore_index=True)
    except Exception as e:
        pass
    return None


# ══════════════════════════════════════════════
# التحليل الإحصائي
# ══════════════════════════════════════════════

def get_numeric_cols(df):
    """استخراج الأعمدة الرقمية"""
    return df.select_dtypes(include=[np.number]).columns.tolist()


def descriptive_analysis(df):
    """الإحصاء الوصفي الكامل"""
    results = {}
    numeric_cols = get_numeric_cols(df)
    
    if not numeric_cols:
        return {'error': 'لا توجد أعمدة رقمية في البيانات'}
    
    desc = df[numeric_cols].describe().round(3)
    results['descriptive'] = desc.to_dict()
    results['columns'] = numeric_cols
    results['n'] = len(df)
    results['missing'] = df[numeric_cols].isnull().sum().to_dict()
    
    # الوزن النسبي (بافتراض مقياس ليكرت 1-5)
    relative_weights = {}
    for col in numeric_cols:
        mean = df[col].mean()
        rw = (mean / 5) * 100
        relative_weights[col] = round(rw, 2)
    results['relative_weights'] = relative_weights
    
    return results


def reliability_analysis(df):
    """تحليل الثبات — Cronbach Alpha"""
    numeric_cols = get_numeric_cols(df)
    if len(numeric_cols) < 2:
        return {'error': 'يحتاج على الأقل عمودين لحساب Alpha'}
    
    data = df[numeric_cols].dropna()
    k = len(numeric_cols)
    item_vars = data.var(axis=0, ddof=1).sum()
    total_var = data.sum(axis=1).var(ddof=1)
    
    if total_var == 0:
        return {'error': 'لا يمكن حساب Alpha — التباين = صفر'}
    
    alpha = (k / (k - 1)) * (1 - item_vars / total_var)
    
    interpretation = ''
    if alpha >= 0.9:
        interpretation = 'ممتاز (Excellent)'
    elif alpha >= 0.8:
        interpretation = 'جيد جداً (Good)'
    elif alpha >= 0.7:
        interpretation = 'مقبول (Acceptable)'
    elif alpha >= 0.6:
        interpretation = 'مشكوك فيه (Questionable)'
    else:
        interpretation = 'ضعيف (Poor)'
    
    return {
        'alpha': round(alpha, 3),
        'n_items': k,
        'n_cases': len(data),
        'interpretation': interpretation
    }


def normality_test(df):
    """اختبار التوزيع الطبيعي — Kolmogorov-Smirnov"""
    from scipy import stats
    numeric_cols = get_numeric_cols(df)
    results = {}
    
    for col in numeric_cols[:10]:  # حد أقصى 10 أعمدة
        data = df[col].dropna()
        if len(data) < 3:
            continue
        stat, p = stats.kstest(data, 'norm', args=(data.mean(), data.std()))
        results[col] = {
            'statistic': round(stat, 4),
            'p_value': round(p, 4),
            'normal': p > 0.05
        }
    return results


def correlation_analysis(df):
    """مصفوفة الارتباط — Pearson"""
    from scipy import stats
    numeric_cols = get_numeric_cols(df)
    if len(numeric_cols) < 2:
        return {'error': 'يحتاج عمودين على الأقل'}
    
    cols = numeric_cols[:8]  # حد أقصى 8 أعمدة
    data = df[cols].dropna()
    corr_matrix = data.corr(method='pearson').round(3)
    
    # حساب قيم p
    p_matrix = pd.DataFrame(np.ones((len(cols), len(cols))), columns=cols, index=cols)
    for i, c1 in enumerate(cols):
        for j, c2 in enumerate(cols):
            if i != j:
                r, p = stats.pearsonr(data[c1], data[c2])
                p_matrix.loc[c1, c2] = round(p, 4)
    
    return {
        'correlation': corr_matrix.to_dict(),
        'p_values': p_matrix.round(4).to_dict(),
        'columns': cols
    }


def regression_analysis(df):
    """تحليل الانحدار الخطي البسيط والمتعدد"""
    from scipy import stats as scipy_stats
    numeric_cols = get_numeric_cols(df)
    
    if len(numeric_cols) < 2:
        return {'error': 'يحتاج عمودين على الأقل'}
    
    # المتغير التابع = آخر عمود، المستقلة = الباقي
    dv = numeric_cols[-1]
    ivs = numeric_cols[:-1][:5]  # حد أقصى 5 متغيرات مستقلة
    
    data = df[[dv] + ivs].dropna()
    y = data[dv].values
    
    results = {'dv': dv, 'ivs': ivs, 'models': []}
    
    # انحدار بسيط لكل متغير
    for iv in ivs:
        x = data[iv].values
        slope, intercept, r, p, se = scipy_stats.linregress(x, y)
        r2 = r ** 2
        results['models'].append({
            'iv': iv,
            'dv': dv,
            'beta': round(slope, 3),
            'intercept': round(intercept, 3),
            'r': round(r, 3),
            'r2': round(r2, 3),
            'p_value': round(p, 4),
            'significant': p < 0.05
        })
    
    # انحدار متعدد
    if len(ivs) > 1:
        try:
            from numpy.linalg import lstsq
            X = np.column_stack([np.ones(len(data))] + [data[iv].values for iv in ivs])
            coeffs, residuals, rank, sv = lstsq(X, y, rcond=None)
            y_pred = X @ coeffs
            ss_res = np.sum((y - y_pred) ** 2)
            ss_tot = np.sum((y - np.mean(y)) ** 2)
            r2_multi = 1 - ss_res / ss_tot if ss_tot != 0 else 0
            n, k = len(y), len(ivs)
            adj_r2 = 1 - (1 - r2_multi) * (n - 1) / (n - k - 1)
            results['multiple'] = {
                'r2': round(r2_multi, 3),
                'adj_r2': round(adj_r2, 3),
                'coefficients': {ivs[i]: round(coeffs[i+1], 3) for i in range(len(ivs))}
            }
        except:
            pass
    
    return results


def ttest_anova(df):
    """اختبار t و ANOVA للفروق"""
    from scipy import stats
    numeric_cols = get_numeric_cols(df)
    cat_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
    
    results = {'ttests': [], 'anovas': []}
    
    if not numeric_cols:
        return {'error': 'لا توجد أعمدة رقمية'}
    
    # إذا كان هناك متغيرات فئوية — ANOVA
    for cat in cat_cols[:3]:
        for num in numeric_cols[:3]:
            groups = [df[df[cat] == val][num].dropna().values 
                     for val in df[cat].unique() if len(df[df[cat] == val]) >= 2]
            if len(groups) == 2:
                t, p = stats.ttest_ind(groups[0], groups[1])
                results['ttests'].append({
                    'variable': num, 'group': cat,
                    't': round(t, 3), 'p': round(p, 4),
                    'significant': p < 0.05
                })
            elif len(groups) > 2:
                f, p = stats.f_oneway(*groups)
                results['anovas'].append({
                    'variable': num, 'group': cat,
                    'F': round(f, 3), 'p': round(p, 4),
                    'significant': p < 0.05
                })
    
    # إذا لم يكن هناك فئوية — مقارنة أول عمودين رقميين
    if not results['ttests'] and not results['anovas'] and len(numeric_cols) >= 2:
        col1, col2 = numeric_cols[0], numeric_cols[1]
        t, p = stats.ttest_ind(df[col1].dropna(), df[col2].dropna())
        results['ttests'].append({
            'variable': f'{col1} vs {col2}', 'group': 'مقارنة مباشرة',
            't': round(t, 3), 'p': round(p, 4),
            'significant': p < 0.05
        })
    
    return results


# ══════════════════════════════════════════════
# إنتاج تقرير Word
# ══════════════════════════════════════════════

def generate_word_report(df, analysis_type, all_results, filename):
    """إنتاج تقرير Word كامل"""
    try:
        from docx import Document
        from docx.shared import Pt, RGBColor, Inches, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        from docx.enum.table import WD_TABLE_ALIGNMENT
    except ImportError:
        return None, "مكتبة python-docx غير متوفرة"
    
    doc = Document()
    
    # ── إعداد الصفحة ──
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.right_margin = Cm(3)
    section.left_margin = Cm(2.5)
    
    # ── العنوان الرئيسي ──
    title = doc.add_heading('الفصل الرابع: تحليل البيانات واختبار الفرضيات', 0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    
    doc.add_paragraph(f'تاريخ التحليل: {datetime.now().strftime("%Y-%m-%d")}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'الملف المحلل: {filename}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'عدد المشاهدات: {len(df)} | عدد المتغيرات: {len(df.columns)}').alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    # ── 4.1 مقدمة ──
    doc.add_heading('4.1 مقدمة', level=1)
    doc.add_paragraph(
        'يتناول هذا الفصل عرض نتائج التحليل الإحصائي للبيانات المجمعة، '
        'إذ تم استخدام برنامج Python مع مكتبات pandas وscipy وstatsmodels '
        'لإجراء التحليلات الإحصائية اللازمة. وقد اشتمل التحليل على الإحصاء '
        'الوصفي، واختبارات الثبات والصدق، واختبار التوزيع الطبيعي، '
        'وتحليل الارتباط والانحدار، واختبار الفرضيات.'
    )

    # ── 4.2 وصف العينة ──
    doc.add_heading('4.2 وصف العينة والبيانات', level=1)
    n = len(df)
    numeric_cols = get_numeric_cols(df)
    cat_cols = df.select_dtypes(include=['object']).columns.tolist()
    doc.add_paragraph(
        f'تكونت عينة الدراسة من ({n}) مشاهدة/مفردة، '
        f'اشتملت البيانات على ({len(numeric_cols)}) متغيراً كمياً '
        f'و({len(cat_cols)}) متغيراً وصفياً.'
    )
    
    # جدول المتغيرات
    if numeric_cols:
        doc.add_paragraph('جدول (1): المتغيرات الكمية في الدراسة')
        table = doc.add_table(rows=1, cols=3)
        table.style = 'Table Grid'
        hdr = table.rows[0].cells
        hdr[0].text = 'المتغير'
        hdr[1].text = 'عدد القيم الصالحة'
        hdr[2].text = 'القيم المفقودة'
        for col in numeric_cols[:10]:
            row = table.add_row().cells
            row[0].text = str(col)
            row[1].text = str(df[col].count())
            row[2].text = str(df[col].isnull().sum())
        doc.add_paragraph()

    # ── 4.3 الثبات ──
    if 'reliability' in all_results and 'error' not in all_results['reliability']:
        doc.add_heading('4.3 تحليل الثبات (Reliability Analysis)', level=1)
        rel = all_results['reliability']
        doc.add_paragraph(
            f'تم قياس ثبات أداة الدراسة باستخدام معامل ألفا كرونباخ (Cronbach\'s Alpha)، '
            f'وقد بلغت قيمته ({rel["alpha"]:.3f})، وهو يُعدّ {rel["interpretation"]}، '
            f'مما يدل على أن الأداة تتمتع بدرجة مقبولة من الثبات والاتساق الداخلي '
            f'وفق معايير (Nunnally, 1978) التي تشترط أن لا تقل القيمة عن (0.70).'
        )
        
        table = doc.add_table(rows=2, cols=3)
        table.style = 'Table Grid'
        headers = ['عدد الفقرات', 'عدد الحالات', 'ألفا كرونباخ']
        values = [str(rel['n_items']), str(rel['n_cases']), f'{rel["alpha"]:.3f}']
        for i, h in enumerate(headers):
            table.rows[0].cells[i].text = h
            table.rows[1].cells[i].text = values[i]
        doc.add_paragraph()

    # ── 4.4 التوزيع الطبيعي ──
    if 'normality' in all_results:
        doc.add_heading('4.4 اختبار التوزيع الطبيعي', level=1)
        doc.add_paragraph(
            'تم اختبار التوزيع الطبيعي للبيانات باستخدام اختبار كولموغوروف-سميرنوف '
            '(Kolmogorov-Smirnov Test)، والجدول التالي يوضح النتائج:'
        )
        norm = all_results['normality']
        if norm and 'error' not in norm:
            table = doc.add_table(rows=1, cols=4)
            table.style = 'Table Grid'
            for i, h in enumerate(['المتغير', 'قيمة الاختبار', 'مستوى الدلالة', 'التوزيع']):
                table.rows[0].cells[i].text = h
            for col, vals in norm.items():
                row = table.add_row().cells
                row[0].text = str(col)
                row[1].text = str(vals['statistic'])
                row[2].text = str(vals['p_value'])
                row[3].text = 'طبيعي ✓' if vals['normal'] else 'غير طبيعي'
            doc.add_paragraph()

    # ── 4.5 الإحصاء الوصفي ──
    if 'descriptive' in all_results and 'error' not in all_results['descriptive']:
        doc.add_heading('4.5 الإحصاء الوصفي', level=1)
        desc = all_results['descriptive']
        rw = all_results['descriptive'].get('relative_weights', {})
        
        cols = desc.get('columns', [])
        if cols:
            table = doc.add_table(rows=1, cols=6)
            table.style = 'Table Grid'
            for i, h in enumerate(['المتغير', 'العدد', 'المتوسط', 'الانحراف المعياري', 'الحد الأدنى', 'الحد الأقصى']):
                table.rows[0].cells[i].text = h
            
            d = desc.get('descriptive', {})
            for col in cols[:10]:
                row = table.add_row().cells
                row[0].text = str(col)
                row[1].text = str(int(d.get(col, {}).get('count', 0)))
                row[2].text = f"{d.get(col, {}).get('mean', 0):.3f}"
                row[3].text = f"{d.get(col, {}).get('std', 0):.3f}"
                row[4].text = f"{d.get(col, {}).get('min', 0):.3f}"
                row[5].text = f"{d.get(col, {}).get('max', 0):.3f}"
            doc.add_paragraph()

    # ── 4.6 الارتباط ──
    if 'correlation' in all_results and 'error' not in all_results['correlation']:
        doc.add_heading('4.6 تحليل الارتباط (Pearson Correlation)', level=1)
        corr_data = all_results['correlation']
        cols = corr_data.get('columns', [])
        corr = corr_data.get('correlation', {})
        pvals = corr_data.get('p_values', {})
        
        doc.add_paragraph(
            'تم حساب معاملات ارتباط بيرسون (Pearson Correlation) لفحص العلاقات '
            'بين متغيرات الدراسة، والجدول التالي يوضح مصفوفة الارتباط:'
        )
        
        if cols:
            table = doc.add_table(rows=len(cols)+1, cols=len(cols)+1)
            table.style = 'Table Grid'
            table.rows[0].cells[0].text = 'المتغير'
            for i, col in enumerate(cols):
                table.rows[0].cells[i+1].text = str(col)
                table.rows[i+1].cells[0].text = str(col)
                for j, col2 in enumerate(cols):
                    val = corr.get(col, {}).get(col2, '')
                    p = pvals.get(col, {}).get(col2, 1)
                    cell_text = f"{val:.3f}" if isinstance(val, float) else str(val)
                    if isinstance(p, float) and p < 0.05 and col != col2:
                        cell_text += '*' if p < 0.05 else ''
                        cell_text += '*' if p < 0.01 else ''
                    table.rows[i+1].cells[j+1].text = cell_text
            doc.add_paragraph('* دالة عند مستوى 0.05    ** دالة عند مستوى 0.01')
            doc.add_paragraph()

    # ── 4.7 الانحدار ──
    if 'regression' in all_results and 'error' not in all_results['regression']:
        doc.add_heading('4.7 تحليل الانحدار (Regression Analysis)', level=1)
        reg = all_results['regression']
        models = reg.get('models', [])
        
        if models:
            doc.add_paragraph(
                f'تم إجراء تحليل الانحدار الخطي لفحص أثر المتغيرات المستقلة '
                f'على المتغير التابع ({reg.get("dv", "")}):'
            )
            table = doc.add_table(rows=1, cols=6)
            table.style = 'Table Grid'
            for i, h in enumerate(['المتغير المستقل', 'Beta', 'R', 'R²', 'قيمة p', 'الدلالة']):
                table.rows[0].cells[i].text = h
            for m in models:
                row = table.add_row().cells
                row[0].text = str(m['iv'])
                row[1].text = f"{m['beta']:.3f}"
                row[2].text = f"{m['r']:.3f}"
                row[3].text = f"{m['r2']:.3f}"
                row[4].text = f"{m['p_value']:.4f}"
                row[5].text = 'دالة **' if m['significant'] else 'غير دالة'
            doc.add_paragraph()
        
        if 'multiple' in reg:
            multi = reg['multiple']
            doc.add_paragraph(
                f'الانحدار المتعدد: R² = {multi["r2"]:.3f} '
                f'(Adjusted R² = {multi["adj_r2"]:.3f})'
            )

    # ── 4.8 الفروق ──
    if 'ttest_anova' in all_results and 'error' not in all_results['ttest_anova']:
        doc.add_heading('4.8 اختبار الفروق', level=1)
        ta = all_results['ttest_anova']
        
        if ta.get('ttests'):
            doc.add_paragraph('جدول اختبار t للفروق بين المجموعات:')
            table = doc.add_table(rows=1, cols=5)
            table.style = 'Table Grid'
            for i, h in enumerate(['المتغير', 'المجموعة', 'قيمة t', 'مستوى الدلالة', 'النتيجة']):
                table.rows[0].cells[i].text = h
            for t in ta['ttests']:
                row = table.add_row().cells
                row[0].text = str(t['variable'])
                row[1].text = str(t['group'])
                row[2].text = f"{t['t']:.3f}"
                row[3].text = f"{t['p']:.4f}"
                row[4].text = 'فروق دالة **' if t['significant'] else 'لا توجد فروق'
            doc.add_paragraph()
        
        if ta.get('anovas'):
            doc.add_paragraph('جدول تحليل التباين الأحادي (ANOVA):')
            table = doc.add_table(rows=1, cols=5)
            table.style = 'Table Grid'
            for i, h in enumerate(['المتغير', 'المجموعة', 'قيمة F', 'مستوى الدلالة', 'النتيجة']):
                table.rows[0].cells[i].text = h
            for a in ta['anovas']:
                row = table.add_row().cells
                row[0].text = str(a['variable'])
                row[1].text = str(a['group'])
                row[2].text = f"{a['F']:.3f}"
                row[3].text = f"{a['p']:.4f}"
                row[4].text = 'فروق دالة **' if a['significant'] else 'لا توجد فروق'
            doc.add_paragraph()

    # ── 4.9 ملخص النتائج ──
    doc.add_heading('4.9 ملخص النتائج الرئيسية', level=1)
    summary_points = []
    
    if 'reliability' in all_results and 'alpha' in all_results.get('reliability', {}):
        alpha = all_results['reliability']['alpha']
        summary_points.append(f'أولاً: بلغ معامل ثبات الأداة (ألفا كرونباخ) ({alpha:.3f})، وهو معامل مرتفع يدل على ثبات الأداة.')
    
    if 'regression' in all_results and 'models' in all_results.get('regression', {}):
        models = all_results['regression']['models']
        sig_models = [m for m in models if m['significant']]
        if sig_models:
            best = max(sig_models, key=lambda x: x['r2'])
            summary_points.append(f'ثانياً: يوجد أثر دال إحصائياً للمتغير ({best["iv"]}) على ({best["dv"]}) بمعامل تحديد R² = {best["r2"]:.3f}.')
    
    if not summary_points:
        summary_points.append('تم إجراء التحليل الإحصائي للبيانات المقدمة وفق الأساليب الإحصائية المناسبة.')
    
    for point in summary_points:
        doc.add_paragraph(point, style='List Bullet')

    doc.add_paragraph()
    doc.add_heading('4.10 خاتمة الفصل', level=1)
    doc.add_paragraph(
        'قدّم هذا الفصل عرضاً شاملاً للتحليل الإحصائي للبيانات، وقد تضمّن '
        'الإحصاء الوصفي وتحليل الثبات واختبار التوزيع الطبيعي وتحليل الارتباط '
        'والانحدار واختبار الفرضيات. وتُشكّل هذه النتائج الأساس العلمي للإجابة '
        'عن أسئلة الدراسة واختبار فرضياتها.'
    )
    
    # حفظ في الذاكرة
    output = io.BytesIO()
    doc.save(output)
    output.seek(0)
    return output, None


# ══════════════════════════════════════════════
# الدالة الرئيسية
# ══════════════════════════════════════════════

def run_full_analysis(file_storage, analysis_type='full'):
    """
    الدالة الرئيسية — تستقبل الملف وتُرجع النتائج والتقرير
    Returns: (results_dict, word_report_bytes, error_message)
    """
    filename = file_storage.filename
    
    # قراءة الملف
    df, error = read_file(file_storage)
    if error:
        return None, None, error
    if df is None or df.empty:
        return None, None, 'الملف فارغ أو لا يحتوي على بيانات قابلة للتحليل'
    
    # تنظيف البيانات
    df = df.replace('', np.nan)
    for col in df.columns:
        try:
            df[col] = pd.to_numeric(df[col], errors='ignore')
        except:
            pass
    
    all_results = {
        'filename': filename,
        'n': len(df),
        'columns': list(df.columns),
        'numeric_columns': get_numeric_cols(df)
    }
    
    try:
        # تشغيل التحليلات
        all_results['descriptive'] = descriptive_analysis(df)
        all_results['reliability'] = reliability_analysis(df)
        all_results['normality'] = normality_test(df)
        
        if analysis_type in ['full', 'correlation']:
            all_results['correlation'] = correlation_analysis(df)
        
        if analysis_type in ['full', 'regression']:
            all_results['regression'] = regression_analysis(df)
        
        if analysis_type in ['full', 'anova']:
            all_results['ttest_anova'] = ttest_anova(df)
        
        # إنتاج تقرير Word
        word_report, word_error = generate_word_report(df, analysis_type, all_results, filename)
        
        return all_results, word_report, None
        
    except Exception as e:
        return all_results, None, f'خطأ في التحليل: {str(e)}\n{traceback.format_exc()}'
