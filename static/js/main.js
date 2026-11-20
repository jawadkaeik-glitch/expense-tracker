/**
 * KashFlow v2 - Modern Minimalist Frontend Controller
 */

document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initUserDropdown();
  initModals();
  initSearchAndFilters();
  initCharts();
  setDefaultDates();
  initSwipeActions();
});

/* ───────────────────────────────────────────────────────────────
 * 1. THEME TOGGLE (Light by Default, Dark Optional)
 * ─────────────────────────────────────────────────────────────── */
function initThemeToggle() {
  const toggleBtn = document.getElementById('themeToggleBtn');
  const icon = document.getElementById('themeToggleIcon');

  // Default to 'light' mode
  const savedTheme = localStorage.getItem('kashflow_theme') || 'light';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeIcon(savedTheme);

  if (toggleBtn) {
    toggleBtn.addEventListener('click', () => {
      const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
      const newTheme = currentTheme === 'light' ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('kashflow_theme', newTheme);
      updateThemeIcon(newTheme);

      // Re-render charts with updated theme colors
      if (window.spendingChart) window.spendingChart.update();
      if (window.comparisonChart) window.comparisonChart.update();
    });
  }

  function updateThemeIcon(theme) {
    if (icon) {
      icon.textContent = theme === 'dark' ? '☀️' : '🌙';
    }
  }
}

/* ───────────────────────────────────────────────────────────────
 * 2. USER AVATAR DROPDOWN
 * ─────────────────────────────────────────────────────────────── */
function initUserDropdown() {
  const btn = document.getElementById('userAvatarBtn');
  const menu = document.getElementById('userDropdown');
  if (!btn || !menu) return;

  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = menu.classList.contains('show');
    menu.classList.toggle('show', !isOpen);
    btn.setAttribute('aria-expanded', !isOpen ? 'true' : 'false');
  });

  document.addEventListener('click', (e) => {
    if (!btn.contains(e.target) && !menu.contains(e.target)) {
      menu.classList.remove('show');
      btn.setAttribute('aria-expanded', 'false');
    }
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      menu.classList.remove('show');
      btn.setAttribute('aria-expanded', 'false');
    }
  });
}

/* ───────────────────────────────────────────────────────────────
 * 3. MODAL MANAGEMENT (Add Expense, Add Income, Quick Add Sheet)
 * ─────────────────────────────────────────────────────────────── */
function initModals() {
  const expenseModal = document.getElementById('expenseModal');
  const incomeModal = document.getElementById('incomeModal');
  const choiceModal = document.getElementById('quickAddChoiceModal');

  const openExpenseBtns = document.querySelectorAll('#openAddModalBtn, .open-expense-modal-btn');
  const openIncomeBtns = document.querySelectorAll('#openAddIncomeModalBtn, .open-income-modal-btn');
  const openChoiceBtn = document.getElementById('openQuickAddChoiceBtn');

  const choiceExpenseBtn = document.getElementById('choiceAddExpenseBtn');
  const choiceIncomeBtn = document.getElementById('choiceAddIncomeBtn');

  const closeBtns = document.querySelectorAll('.close-modal-trigger');

  // Mobile Bottom Tab "+" button toggles the choice action sheet
  if (openChoiceBtn && choiceModal) {
    openChoiceBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      choiceModal.classList.toggle('active');
    });
  }

  if (choiceExpenseBtn && choiceModal) {
    choiceExpenseBtn.addEventListener('click', () => {
      choiceModal.classList.remove('active');
      openExpenseModal();
    });
  }

  if (choiceIncomeBtn && choiceModal) {
    choiceIncomeBtn.addEventListener('click', () => {
      choiceModal.classList.remove('active');
      openIncomeModal();
    });
  }

  openExpenseBtns.forEach(b => {
    b.addEventListener('click', (e) => {
      e.preventDefault();
      openExpenseModal();
    });
  });

  openIncomeBtns.forEach(b => {
    b.addEventListener('click', (e) => {
      e.preventDefault();
      openIncomeModal();
    });
  });

  closeBtns.forEach(b => {
    b.addEventListener('click', () => {
      closeAllModals();
    });
  });

  // Backdrop click to close
  [expenseModal, incomeModal, choiceModal].forEach(m => {
    if (m) {
      m.addEventListener('click', (e) => {
        if (e.target === m) closeAllModals();
      });
    }
  });

  // Edit Expense delegation
  document.addEventListener('click', (e) => {
    const editExp = e.target.closest('.edit-modal-btn');
    if (editExp) {
      const id = editExp.getAttribute('data-id');
      const desc = editExp.getAttribute('data-description');
      const amt = editExp.getAttribute('data-amount');
      const cat = editExp.getAttribute('data-category');
      const date = editExp.getAttribute('data-date');
      const method = editExp.getAttribute('data-payment-method');
      const notes = editExp.getAttribute('data-notes');

      if (expenseModal) {
        document.getElementById('modalTitle').textContent = 'Edit Expense';
        document.getElementById('modalSubmitBtn').textContent = 'Update Expense';
        document.getElementById('modalExpenseForm').action = `/edit/${id}`;
        document.getElementById('modalDescription').value = desc || '';
        document.getElementById('modalAmount').value = amt || '';
        document.getElementById('modalCategory').value = cat || 'General';
        document.getElementById('modalDate').value = date || '';
        document.getElementById('modalPaymentMethod').value = method || 'Card';
        document.getElementById('modalNotes').value = notes || '';
        expenseModal.classList.add('active');
      }
      return;
    }

    const editInc = e.target.closest('.edit-income-modal-btn');
    if (editInc) {
      const id = editInc.getAttribute('data-id');
      const desc = editInc.getAttribute('data-description');
      const amt = editInc.getAttribute('data-amount');
      const cat = editInc.getAttribute('data-category');
      const date = editInc.getAttribute('data-date');
      const source = editInc.getAttribute('data-source');
      const notes = editInc.getAttribute('data-notes');

      if (incomeModal) {
        document.getElementById('modalIncomeTitle').textContent = 'Edit Income';
        document.getElementById('modalIncomeSubmitBtn').textContent = 'Update Income';
        document.getElementById('modalIncomeForm').action = `/edit-income/${id}`;
        document.getElementById('modalIncomeDescription').value = desc || '';
        document.getElementById('modalIncomeAmount').value = amt || '';
        document.getElementById('modalIncomeCategory').value = cat || 'Salary';
        document.getElementById('modalIncomeDate').value = date || '';
        document.getElementById('modalIncomeSource').value = source || 'Bank Transfer';
        document.getElementById('modalIncomeNotes').value = notes || '';
        incomeModal.classList.add('active');
      }
    }
  });

  function openExpenseModal() {
    if (!expenseModal) return;
    document.getElementById('modalTitle').textContent = 'Add Expense';
    document.getElementById('modalSubmitBtn').textContent = 'Save Expense';
    const form = document.getElementById('modalExpenseForm');
    form.action = '/add';
    form.reset();
    setDefaultDates();
    expenseModal.classList.add('active');
  }

  function openIncomeModal() {
    if (!incomeModal) return;
    document.getElementById('modalIncomeTitle').textContent = 'Add Income';
    document.getElementById('modalIncomeSubmitBtn').textContent = 'Save Income';
    const form = document.getElementById('modalIncomeForm');
    form.action = '/add-income';
    form.reset();
    setDefaultDates();
    incomeModal.classList.add('active');
  }

  function closeAllModals() {
    if (expenseModal) expenseModal.classList.remove('active');
    if (incomeModal) incomeModal.classList.remove('active');
    if (choiceModal) choiceModal.classList.remove('active');
  }
}

/* ───────────────────────────────────────────────────────────────
 * 4. CLIENT-SIDE SEARCH & FILTERING
 * ─────────────────────────────────────────────────────────────── */
function initSearchAndFilters() {
  const search = document.getElementById('tableSearchInput');
  const filter = document.getElementById('tableCategoryFilter');
  if (!search && !filter) return;

  const performFilter = () => {
    const q = search ? search.value.toLowerCase().trim() : '';
    const cat = filter ? filter.value : 'all';
    const rows = document.querySelectorAll('.data-row');
    let matched = 0;

    rows.forEach(r => {
      const desc = r.getAttribute('data-description') || '';
      const rowCat = r.getAttribute('data-category') || '';
      const notes = r.getAttribute('data-notes') || '';

      const matchSearch = !q || desc.includes(q) || notes.includes(q);
      const matchCat = cat === 'all' || rowCat === cat;

      if (matchSearch && matchCat) {
        r.style.display = '';
        matched++;
      } else {
        r.style.display = 'none';
      }
    });

    const empty = document.getElementById('tableEmptySearchMsg');
    if (empty) {
      empty.style.display = (matched === 0 && rows.length > 0) ? 'block' : 'none';
    }
  };

  if (search) search.addEventListener('input', performFilter);
  if (filter) filter.addEventListener('change', performFilter);
}

/* ───────────────────────────────────────────────────────────────
 * 5. CHART.JS VISUALIZATIONS
 * ─────────────────────────────────────────────────────────────── */
function initCharts() {
  if (typeof Chart === 'undefined') return;

  // Doughnut Chart: Category Spending
  const spendingCanvas = document.getElementById('spendingChart');
  if (spendingCanvas && window.spendingChartData) {
    const data = window.spendingChartData;
    const ctx = spendingCanvas.getContext('2d');
    const colors = ['#059669', '#2563eb', '#d97706', '#e11d48', '#8b5cf6', '#06b6d4', '#64748b'];

    window.spendingChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: data.labels || [],
        datasets: [{
          data: data.data || [],
          backgroundColor: colors.slice(0, (data.labels || []).length),
          borderWidth: 0,
          hoverOffset: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 10,
              padding: 12,
              font: { size: 12 }
            }
          }
        },
        cutout: '68%'
      }
    });
  }

  // Bar Chart: 6-Month Income vs Expense Trend
  const compCanvas = document.getElementById('comparisonChart');
  if (compCanvas && window.comparisonChartData) {
    const compData = window.comparisonChartData;
    const ctx = compCanvas.getContext('2d');

    let datasets = [];
    if (compData.income && compData.expenses) {
      datasets = [
        {
          label: 'Income ($)',
          data: compData.income,
          backgroundColor: '#059669',
          borderRadius: 4
        },
        {
          label: 'Expenses ($)',
          data: compData.expenses,
          backgroundColor: '#e11d48',
          borderRadius: 4
        }
      ];
    } else {
      datasets = [{
        label: 'Monthly ($)',
        data: compData.data || [],
        backgroundColor: ['#059669', '#e11d48', '#2563eb'],
        borderRadius: 4
      }];
    }

    window.comparisonChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: compData.labels || [],
        datasets: datasets
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: Boolean(compData.income),
            position: 'top',
            labels: { boxWidth: 10, font: { size: 12 } }
          }
        },
        scales: {
          x: { grid: { display: false } },
          y: { beginAtZero: true, grid: { color: 'rgba(150, 150, 150, 0.1)' } }
        }
      }
    });
  }
}

/* ───────────────────────────────────────────────────────────────
 * 6. DEFAULT DATE SETUP
 * ─────────────────────────────────────────────────────────────── */
function setDefaultDates() {
  const today = new Date().toISOString().split('T')[0];
  ['modalDate', 'modalIncomeDate'].forEach(id => {
    const el = document.getElementById(id);
    if (el && !el.value) el.value = today;
  });
}

/* ───────────────────────────────────────────────────────────────
 * 7. MOBILE TOUCH SWIPE GESTURES
 * ─────────────────────────────────────────────────────────────── */
function initSwipeActions() {
  const rows = document.querySelectorAll('.data-row');

  rows.forEach(r => {
    let startX = 0;
    let diffX = 0;

    r.addEventListener('touchstart', (e) => {
      startX = e.touches[0].clientX;
    }, { passive: true });

    r.addEventListener('touchmove', (e) => {
      diffX = e.touches[0].clientX - startX;
      if (Math.abs(diffX) > 15 && Math.abs(diffX) < 100) {
        r.style.transform = `translateX(${diffX}px)`;
      }
    }, { passive: true });

    r.addEventListener('touchend', () => {
      r.style.transform = 'translateX(0)';
      if (diffX < -65) {
        // Swipe Left -> Delete
        const delForm = r.querySelector('form[action*="/delete"]');
        if (delForm && confirm('Delete this record?')) {
          delForm.submit();
        }
      } else if (diffX > 65) {
        // Swipe Right -> Edit
        const editBtn = r.querySelector('.edit-modal-btn, .edit-income-modal-btn');
        if (editBtn) editBtn.click();
      }
      startX = 0;
      diffX = 0;
    });
  });
}
