/**
 * KashFlow - Frontend Interactive Module
 * Handles UI interactions, theme toggling, modal dialogs, Chart.js visualizations,
 * touch gestures, and quick spend logging.
 */

document.addEventListener('DOMContentLoaded', () => {
  // Initialize all core interactive components when DOM is fully loaded
  initThemeToggle();
  initSearchAndFilters();
  initModals();
  initCharts();
  initFAB();
  initAdvancedToggles();
  setDefaultDates();
  initUserDropdown();
  initQuickChips();
  initRepeatLastSpend();
  initSwipeActions();
});

/* ───────────────────────────────────────────────────────────────
 * 1. USER AVATAR DROPDOWN MENU
 * Controls opening, closing, outside click, and ESC key handlers for user profile menu.
 * ─────────────────────────────────────────────────────────────── */
function initUserDropdown() {
  const btn = document.getElementById('userAvatarBtn');
  const dropdown = document.getElementById('userDropdown');
  if (!btn || !dropdown) return;

  // Toggle menu on avatar button click
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const isOpen = dropdown.classList.contains('show');
    if (isOpen) {
      dropdown.classList.remove('show');
      btn.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    } else {
      dropdown.classList.add('show');
      btn.classList.add('open');
      btn.setAttribute('aria-expanded', 'true');
    }
  });

  // Close dropdown when clicking outside
  document.addEventListener('click', (e) => {
    if (!btn.contains(e.target) && !dropdown.contains(e.target)) {
      dropdown.classList.remove('show');
      btn.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
  });

  // Close dropdown on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      dropdown.classList.remove('show');
      btn.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
  });
}

/* ───────────────────────────────────────────────────────────────
 * 2. LIGHT / DARK THEME TOGGLE
 * Persists theme preference in localStorage & updates CSS data-theme attributes.
 * ─────────────────────────────────────────────────────────────── */
function initThemeToggle() {
  const toggleBtns = document.querySelectorAll('#themeToggleBtn, #menuThemeToggleBtn');

  // Load saved theme preference or default to dark mode
  const savedTheme = localStorage.getItem('expense_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', savedTheme);
  toggleBtns.forEach(btn => updateThemeIcon(btn, savedTheme));

  toggleBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const currentTheme = document.documentElement.getAttribute('data-theme');
      const newTheme = currentTheme === 'light' ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', newTheme);
      localStorage.setItem('expense_theme', newTheme);
      toggleBtns.forEach(b => updateThemeIcon(b, newTheme));

      // Refresh Chart.js instances to adjust chart colors dynamically
      if (window.spendingChart) window.spendingChart.update();
      if (window.incomeChart) window.incomeChart.update();
      if (window.comparisonChart) window.comparisonChart.update();
    });
  });
}

function updateThemeIcon(btn, theme) {
  if (!btn) return;
  btn.innerHTML = theme === 'light' ? '🌙 Switch to Dark' : '☀️ Switch to Light';
}

/* ───────────────────────────────────────────────────────────────
 * 3. MODAL DIALOG MANAGEMENT
 * Handles opening, editing, closing, and mobile action sheet toggling.
 * ─────────────────────────────────────────────────────────────── */
function initModals() {
  const openExpenseModalBtns = document.querySelectorAll('#openAddModalBtn, .open-expense-modal-btn');
  const openIncomeModalBtns = document.querySelectorAll('#openAddIncomeModalBtn, .open-income-modal-btn');

  const expenseModal = document.getElementById('expenseModal');
  const incomeModal = document.getElementById('incomeModal');
  const choiceModal = document.getElementById('quickAddChoiceModal');
  const openChoiceBtn = document.getElementById('openQuickAddChoiceBtn');
  const choiceExpenseBtn = document.getElementById('choiceAddExpenseBtn');
  const choiceIncomeBtn = document.getElementById('choiceAddIncomeBtn');

  const closeModalBtns = document.querySelectorAll('.close-modal-trigger');

  // Mobile Bottom Tab "+" Quick Add Button Listener (Toggles Choice Action Sheet)
  if (openChoiceBtn && choiceModal) {
    openChoiceBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      choiceModal.classList.toggle('active');
    });
  }

  // Quick Add Choice: Add Expense Selected
  if (choiceExpenseBtn && choiceModal) {
    choiceExpenseBtn.addEventListener('click', () => {
      choiceModal.classList.remove('active');
      openAddExpenseModal();
    });
  }

  // Quick Add Choice: Add Income Selected
  if (choiceIncomeBtn && choiceModal) {
    choiceIncomeBtn.addEventListener('click', () => {
      choiceModal.classList.remove('active');
      openAddIncomeModal();
    });
  }

  // Open Expense Modal
  openExpenseModalBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openAddExpenseModal();
    });
  });

  // Open Income Modal
  openIncomeModalBtns.forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      openAddIncomeModal();
    });
  });

  // Close modals on cancel/close button trigger
  closeModalBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      if (expenseModal) expenseModal.classList.remove('active');
      if (incomeModal) incomeModal.classList.remove('active');
      if (choiceModal) choiceModal.classList.remove('active');
    });
  });

  // Close modals when clicking backdrop overlay
  [expenseModal, incomeModal, choiceModal].forEach(modal => {
    if (modal) {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('active');
      });
    }
  });

  // Event Delegation for Edit Expense and Edit Income Buttons in Data Tables
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

  modalTitle.textContent = 'Add Income';
  submitBtn.textContent = 'Save Income';
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

/* ───────────────────────────────────────────────────────────────
 * 4. LIVE CLIENT-SIDE TABLE SEARCH & CATEGORY FILTERING
 * Filter table rows dynamically in real time as user types.
 * ─────────────────────────────────────────────────────────────── */
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

    const emptyMsg = document.getElementById('tableEmptySearchMsg');
    if (emptyMsg) {
      emptyMsg.style.display = (visibleCount === 0 && rows.length > 0) ? 'block' : 'none';
    }
  };

  if (searchInput) searchInput.addEventListener('input', filterRows);
  if (categorySelect) categorySelect.addEventListener('change', filterRows);
}

/* ───────────────────────────────────────────────────────────────
 * 5. CHART.JS VISUALIZATIONS
 * Renders spending donut charts and month-over-month trend bar charts.
 * ─────────────────────────────────────────────────────────────── */
function initCharts() {
  if (typeof Chart === 'undefined') return;

  const spendingCanvas = document.getElementById('spendingChart');
  if (spendingCanvas && window.spendingChartData) {
    const data = window.spendingChartData;
    const ctx = spendingCanvas.getContext('2d');

    const colors = [
      '#6366f1', '#10b981', '#f59e0b', '#ef4444',
      '#8b5cf6', '#06b6d4', '#ec4899', '#64748b'
    ];

    window.spendingChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: data.labels || [],
        datasets: [{
          data: data.data || [],
          backgroundColor: colors.slice(0, (data.labels || []).length),
          borderWidth: 0,
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 12,
              padding: 15,
              color: getComputedStyle(document.documentElement).getPropertyValue('--text-muted').trim()
            }
          }
        },
        cutout: '70%'
      }
    });
  }

  // Month-Over-Month Income vs Expenses Comparison Bar Chart
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
          backgroundColor: '#10b981',
          borderRadius: 6
        },
        {
          label: 'Expenses ($)',
          data: compData.expenses,
          backgroundColor: '#ef4444',
          borderRadius: 6
        }
      ];
    } else {
      datasets = [{
        label: 'Monthly Stats ($)',
        data: compData.data || [],
        backgroundColor: ['#10b981', '#ef4444', '#6366f1'],
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
}

/* ───────────────────────────────────────────────────────────────
 * 6. FLOATING ACTION BUTTON (FAB) & SPEED DIAL
 * ─────────────────────────────────────────────────────────────── */
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

  document.addEventListener('click', (e) => {
    if (!e.target.closest('#fabContainer')) {
      if (fabOptions) fabOptions.classList.remove('open');
      if (fabMain) fabMain.classList.remove('open');
    }
  });
}

/* ───────────────────────────────────────────────────────────────
 * 7. ADVANCED FORM FIELD EXPANDERS
 * ─────────────────────────────────────────────────────────────── */
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

/* ───────────────────────────────────────────────────────────────
 * 8. DEFAULT DATE INITIALIZER
 * Sets today's YYYY-MM-DD as default for date input fields.
 * ─────────────────────────────────────────────────────────────── */
function setDefaultDates() {
  const today = new Date().toISOString().split('T')[0];
  ['modalDate', 'modalIncomeDate'].forEach(id => {
    const el = document.getElementById(id);
    if (el && !el.value) el.value = today;
  });
}

/* ───────────────────────────────────────────────────────────────
 * 9. QUICK EMOJI CATEGORY CHIPS (<5s LOGGING)
 * Selecting an emoji chip populates the category & description instantly.
 * ─────────────────────────────────────────────────────────────── */
function initQuickChips() {
  const chips = document.querySelectorAll('.quick-chip-btn');
  const catSelect = document.getElementById('modalCategory');
  const descInput = document.getElementById('modalDescription');

  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      chips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');

      const cat = chip.getAttribute('data-cat');
      const desc = chip.getAttribute('data-desc');

      if (catSelect && cat) catSelect.value = cat;
      if (descInput && desc) descInput.value = desc;
    });
  });
}

/* ───────────────────────────────────────────────────────────────
 * 10. REPEAT LAST SPEND (1-TAP LOGGING)
 * Fills in the last logged expense details in 1 tap.
 * ─────────────────────────────────────────────────────────────── */
function initRepeatLastSpend() {
  const repeatBtn = document.getElementById('repeatLastSpendBtn');
  if (!repeatBtn) return;

  repeatBtn.addEventListener('click', () => {
    const desc = repeatBtn.getAttribute('data-desc');
    const amt = repeatBtn.getAttribute('data-amt');
    const cat = repeatBtn.getAttribute('data-cat');

    const descInput = document.getElementById('modalDescription');
    const amtInput = document.getElementById('modalAmount');
    const catSelect = document.getElementById('modalCategory');

    if (descInput && desc) descInput.value = desc;
    if (amtInput && amt) amtInput.value = amt;
    if (catSelect && cat) catSelect.value = cat;
  });
}

/* ───────────────────────────────────────────────────────────────
 * 11. MOBILE TOUCH SWIPE GESTURES
 * Swipe Left -> Delete item; Swipe Right -> Edit item.
 * ─────────────────────────────────────────────────────────────── */
function initSwipeActions() {
  const rows = document.querySelectorAll('.data-row');

  rows.forEach(row => {
    let startX = 0;
    let currentX = 0;

    row.addEventListener('touchstart', (e) => {
      startX = e.touches[0].clientX;
    }, { passive: true });

    row.addEventListener('touchmove', (e) => {
      currentX = e.touches[0].clientX;
      const diffX = currentX - startX;

      if (Math.abs(diffX) > 20 && Math.abs(diffX) < 120) {
        row.style.transform = `translateX(${diffX}px)`;
      }
    }, { passive: true });

    row.addEventListener('touchend', () => {
      const diffX = currentX - startX;
      row.style.transform = 'translateX(0)';

      if (diffX < -70) {
        // Swipe Left -> Trigger Delete confirmation
        const deleteForm = row.querySelector('form[action*="/delete"]');
        if (deleteForm && confirm('Delete this item?')) {
          deleteForm.submit();
        }
      } else if (diffX > 70) {
        // Swipe Right -> Open Edit Modal
        const editBtn = row.querySelector('.edit-modal-btn, .edit-income-modal-btn');
        if (editBtn) editBtn.click();
      }

      startX = 0;
      currentX = 0;
    });
  });
}
