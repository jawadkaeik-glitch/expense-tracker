// KashFlow Interactive Features
document.addEventListener('DOMContentLoaded', () => {
  initThemeToggle();
  initSearchAndFilters();
  initModals();
  initCharts();
  initFAB();
  initAdvancedToggles();
  setDefaultDates();
  initUserDropdown();
});

/* User Avatar Dropdown */
function initUserDropdown() {
  const btn = document.getElementById('userAvatarBtn');
  if (!btn) return;
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    btn.classList.toggle('open');
  });
  document.addEventListener('click', () => btn.classList.remove('open'));
}


/* Theme Toggle */
function initThemeToggle() {
  const toggleBtn = document.getElementById('themeToggleBtn');
  if (!toggleBtn) return;

  const savedTheme = localStorage.getItem('expense_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
  updateThemeIcon(toggleBtn, savedTheme);

  toggleBtn.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    const newTheme = currentTheme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('expense_theme', newTheme);
    updateThemeIcon(toggleBtn, newTheme);

    // Refresh charts if present
    if (window.spendingChart) window.spendingChart.update();
    if (window.incomeChart) window.incomeChart.update();
    if (window.comparisonChart) window.comparisonChart.update();
  });
}

function updateThemeIcon(btn, theme) {
  btn.innerHTML = theme === 'light' ? '🌙 Dark Mode' : '☀️ Light Mode';
}

/* Modal Handling */
function initModals() {
  const openExpenseModalBtns = document.querySelectorAll('#openAddModalBtn, .open-expense-modal-btn');
  const openIncomeModalBtns = document.querySelectorAll('#openAddIncomeModalBtn, .open-income-modal-btn');

  const expenseModal = document.getElementById('expenseModal');
  const incomeModal = document.getElementById('incomeModal');
  const closeModalBtns = document.querySelectorAll('.close-modal-trigger');

  openExpenseModalBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openAddExpenseModal();
    });
  });

  openIncomeModalBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openAddIncomeModal();
    });
  });


  closeModalBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      if (expenseModal) expenseModal.classList.remove('active');
      if (incomeModal) incomeModal.classList.remove('active');
    });
  });

  [expenseModal, incomeModal].forEach(modal => {
    if (modal) {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('active');
      });
    }
  });

  // Event Delegation for Edit Expense and Edit Income
  document.addEventListener('click', (e) => {
    const editExpBtn = e.target.closest('.edit-modal-btn');
    if (editExpBtn) {
      const id = editExpBtn.getAttribute('data-id');
      const description = editExpBtn.getAttribute('data-description');
      const amount = editExpBtn.getAttribute('data-amount');
      const category = editExpBtn.getAttribute('data-category');
      const date = editExpBtn.getAttribute('data-date');
      const paymentMethod = editExpBtn.getAttribute('data-payment-method');
      const notes = editExpBtn.getAttribute('data-notes');
      openEditExpenseModal(id, description, amount, category, date, paymentMethod, notes);
      return;
    }

    const editIncBtn = e.target.closest('.edit-income-modal-btn');
    if (editIncBtn) {
      const id = editIncBtn.getAttribute('data-id');
      const description = editIncBtn.getAttribute('data-description');
      const amount = editIncBtn.getAttribute('data-amount');
      const category = editIncBtn.getAttribute('data-category');
      const date = editIncBtn.getAttribute('data-date');
      const source = editIncBtn.getAttribute('data-source');
      const notes = editIncBtn.getAttribute('data-notes');
      openEditIncomeModal(id, description, amount, category, date, source, notes);
      return;
    }

    const deleteBtn = e.target.closest('form button.btn-danger, form .btn-danger');
    if (deleteBtn) {
      if (!confirm('Are you sure you want to delete this item?')) {
        e.preventDefault();
      }
      return;
    }
  });


}

function openAddExpenseModal() {
  const modal = document.getElementById('expenseModal');
  const form = document.getElementById('modalExpenseForm');
  const modalTitle = document.getElementById('modalTitle');
  const submitBtn = document.getElementById('modalSubmitBtn');

  if (!modal || !form) return;

  modalTitle.textContent = 'Add New Expense';
  submitBtn.textContent = 'Add Expense';
  form.action = '/add';
  form.reset();

  const dateInput = document.getElementById('modalDate');
  if (dateInput) dateInput.value = new Date().toISOString().split('T')[0];

  modal.classList.add('active');
}

function openEditExpenseModal(id, description, amount, category, date, paymentMethod, notes) {
  const modal = document.getElementById('expenseModal');
  const form = document.getElementById('modalExpenseForm');
  const modalTitle = document.getElementById('modalTitle');
  const submitBtn = document.getElementById('modalSubmitBtn');

  if (!modal || !form) return;

  modalTitle.textContent = 'Edit Expense';
  submitBtn.textContent = 'Update Expense';
  form.action = `/edit/${id}`;

  document.getElementById('modalDescription').value = description;
  document.getElementById('modalAmount').value = amount;
  document.getElementById('modalCategory').value = category;
  document.getElementById('modalDate').value = date;
  document.getElementById('modalPaymentMethod').value = paymentMethod;
  document.getElementById('modalNotes').value = notes || '';

  modal.classList.add('active');
}

function openAddIncomeModal() {
  const modal = document.getElementById('incomeModal');
  const form = document.getElementById('modalIncomeForm');
  const modalTitle = document.getElementById('modalIncomeTitle');
  const submitBtn = document.getElementById('modalIncomeSubmitBtn');

  if (!modal || !form) return;

  modalTitle.textContent = 'Add New Income';
  submitBtn.textContent = 'Add Income';
  form.action = '/add-income';
  form.reset();

  const dateInput = document.getElementById('modalIncomeDate');
  if (dateInput) dateInput.value = new Date().toISOString().split('T')[0];

  modal.classList.add('active');
}

function openEditIncomeModal(id, description, amount, category, date, source, notes) {
  const modal = document.getElementById('incomeModal');
  const form = document.getElementById('modalIncomeForm');
  const modalTitle = document.getElementById('modalIncomeTitle');
  const submitBtn = document.getElementById('modalIncomeSubmitBtn');

  if (!modal || !form) return;

  modalTitle.textContent = 'Edit Income';
  submitBtn.textContent = 'Update Income';
  form.action = `/edit-income/${id}`;

  document.getElementById('modalIncomeDescription').value = description;
  document.getElementById('modalIncomeAmount').value = amount;
  document.getElementById('modalIncomeCategory').value = category;
  document.getElementById('modalIncomeDate').value = date;
  document.getElementById('modalIncomeSource').value = source;
  document.getElementById('modalIncomeNotes').value = notes || '';

  modal.classList.add('active');
}

/* Client-side Live Table Filter & Search */
function initSearchAndFilters() {
  const searchInput = document.getElementById('tableSearchInput');
  const categorySelect = document.getElementById('tableCategoryFilter');

  if (!searchInput && !categorySelect) return;

  const filterRows = () => {
    const query = searchInput ? searchInput.value.toLowerCase().trim() : '';
    const selectedCategory = categorySelect ? categorySelect.value : 'all';
    const rows = document.querySelectorAll('.data-row');
    let visibleCount = 0;

    rows.forEach(row => {
      const desc = row.getAttribute('data-description') || '';
      const cat = row.getAttribute('data-category') || '';
      const notes = row.getAttribute('data-notes') || '';

      const matchesSearch = !query || desc.includes(query) || notes.includes(query);
      const matchesCategory = selectedCategory === 'all' || cat === selectedCategory;

      if (matchesSearch && matchesCategory) {
        row.style.display = '';
        visibleCount++;
      } else {
        row.style.display = 'none';
      }
    });

    const emptyRow = document.getElementById('noResultsRow');
    if (emptyRow) {
      emptyRow.style.display = (visibleCount === 0 && rows.length > 0) ? '' : 'none';
    }
  };

  if (searchInput) searchInput.addEventListener('input', filterRows);
  if (categorySelect) categorySelect.addEventListener('change', filterRows);
}

/* Chart.js Initialization */
function initCharts() {
  const categoryCanvas = document.getElementById('categoryChart');
  const incomeCanvas = document.getElementById('incomeChart');
  const comparisonCanvas = document.getElementById('comparisonChart');

  // Expense Doughnut
  if (categoryCanvas && window.chartCategoryData) {
    const ctx = categoryCanvas.getContext('2d');
    window.spendingChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: window.chartCategoryData.labels,
        datasets: [{
          data: window.chartCategoryData.data,
          backgroundColor: [
            '#f59e0b', '#3b82f6', '#a855f7', '#ec4899', '#06b6d4', '#10b981', '#94a3b8'
          ],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() }
          }
        },
        cutout: '70%'
      }
    });
  }

  // Income Doughnut
  if (incomeCanvas && window.chartIncomeData) {
    const ctx = incomeCanvas.getContext('2d');
    window.incomeChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: window.chartIncomeData.labels,
        datasets: [{
          data: window.chartIncomeData.data,
          backgroundColor: [
            '#10b981', '#6366f1', '#06b6d4', '#a855f7', '#ec4899', '#f59e0b', '#3b82f6'
          ],
          borderWidth: 0
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() }
          }
        },
        cutout: '70%'
      }
    });
  }

  // Comparison Bar Chart (Income vs Expense 6-Month Trend & Summary)
  if (comparisonCanvas && window.chartComparisonData) {
    const ctx = comparisonCanvas.getContext('2d');
    const compData = window.chartComparisonData;

    let datasets = [];
    if (compData.income && compData.expenses) {
      datasets = [
        {
          label: 'Income ($)',
          data: compData.income,
          backgroundColor: 'rgba(16, 185, 129, 0.75)',
          borderColor: '#10b981',
          borderWidth: 1,
          borderRadius: 6
        },
        {
          label: 'Expenses ($)',
          data: compData.expenses,
          backgroundColor: 'rgba(239, 68, 68, 0.75)',
          borderColor: '#ef4444',
          borderWidth: 1,
          borderRadius: 6
        }
      ];
    } else {
      datasets = [{
        label: 'Amount ($)',
        data: compData.data || [],
        backgroundColor: [
          'rgba(16, 185, 129, 0.75)',
          'rgba(239, 68, 68, 0.75)',
          'rgba(99, 102, 241, 0.75)'
        ],
        borderColor: ['#10b981', '#ef4444', '#6366f1'],
        borderWidth: 1,
        borderRadius: 8
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
            display: compData.income ? true : false,
            position: 'top',
            labels: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() }
          }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() }
          },
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(255,255,255,0.05)' },
            ticks: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() }
          }
        }
      }
    });
  }

  // Trend Line Chart (Monthly Expense History)
  const trendCanvas = document.getElementById('trendChart');
  if (trendCanvas && window.chartTrendData) {
    const ctx = trendCanvas.getContext('2d');
    const trendData = window.chartTrendData;
    window.trendChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels: trendData.labels || [],
        datasets: [{
          label: 'Expenses ($)',
          data: trendData.expenses || trendData.data || [],
          borderColor: '#ef4444',
          backgroundColor: 'rgba(239, 68, 68, 0.15)',
          fill: true,
          tension: 0.35,
          borderWidth: 2,
          pointRadius: 4
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false }
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() }
          },
          y: {
            beginAtZero: true,
            grid: { color: 'rgba(255,255,255,0.05)' },
            ticks: { color: getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim() }
          }
        }
      }
    });
  }
}


/* ===== FLOATING ACTION BUTTON ===== */
function initFAB() {
  const fabMain = document.getElementById('fabMain');
  const fabOptions = document.getElementById('fabOptions');
  const fabAddExpense = document.getElementById('fabAddExpense');
  const fabAddIncome = document.getElementById('fabAddIncome');

  if (!fabMain) return;

  fabMain.addEventListener('click', () => {
    const isOpen = fabOptions.classList.contains('open');
    fabOptions.classList.toggle('open', !isOpen);
    fabMain.classList.toggle('open', !isOpen);
  });

  if (fabAddExpense) {
    fabAddExpense.addEventListener('click', () => {
      fabOptions.classList.remove('open');
      fabMain.classList.remove('open');
      openAddExpenseModal();
    });
  }

  if (fabAddIncome) {
    fabAddIncome.addEventListener('click', () => {
      fabOptions.classList.remove('open');
      fabMain.classList.remove('open');
      openAddIncomeModal();
    });
  }

  // Close FAB when clicking elsewhere
  document.addEventListener('click', (e) => {
    if (!e.target.closest('#fabContainer')) {
      fabOptions.classList.remove('open');
      fabMain.classList.remove('open');
    }
  });
}

/* ===== ADVANCED OPTIONS TOGGLE ===== */
function initAdvancedToggles() {
  function setupToggle(toggleId, fieldsId, arrowId) {
    const btn = document.getElementById(toggleId);
    const fields = document.getElementById(fieldsId);
    const arrow = document.getElementById(arrowId);
    if (!btn || !fields) return;
    btn.addEventListener('click', () => {
      const open = fields.classList.toggle('open');
      if (arrow) arrow.textContent = open ? '▾' : '▸';
    });
  }
  setupToggle('expenseAdvancedToggle', 'expenseAdvancedFields', 'expenseAdvancedArrow');
  setupToggle('incomeAdvancedToggle',  'incomeAdvancedFields',  'incomeAdvancedArrow');
}

/* ===== SET DEFAULT DATES ===== */
function setDefaultDates() {
  const today = new Date().toISOString().split('T')[0];
  ['modalDate', 'modalIncomeDate'].forEach(id => {
    const el = document.getElementById(id);
    if (el && !el.value) el.value = today;
  });
}
