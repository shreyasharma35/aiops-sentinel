/**
 * AIOps Sentinel - E-Commerce Storefront Interactive Logic
 * Ingests Fake Store API catalogue, manages SQLite session cart,
 * drives checkout & payment pipeline, and reflects live telemetry faults.
 */

// Generate or retrieve persistent browser session ID
let SESSION_ID = localStorage.getItem("sentinel_cart_session");
if (!SESSION_ID) {
  SESSION_ID = "sess-" + Math.random().toString(36).substring(2, 10);
  localStorage.setItem("sentinel_cart_session", SESSION_ID);
}

let allProducts = [];
let currentCategory = "all";
let activeCart = { items: [], total_amount: 0, total_items: 0 };

document.addEventListener("DOMContentLoaded", () => {
  initCategories();
  loadProducts();
  fetchCart();
  setupEventListeners();
  pollChaosStatus();
  setInterval(pollChaosStatus, 3000);
});

function setupEventListeners() {
  // Search input
  const searchInput = document.getElementById("searchInput");
  if (searchInput) {
    let debounceTimer;
    searchInput.addEventListener("input", (e) => {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(() => {
        loadProducts(currentCategory, e.target.value.trim());
      }, 300);
    });
  }

  // Cart Drawer open/close
  document.getElementById("cartBtn").addEventListener("click", openCartDrawer);
  document.getElementById("drawerCloseBtn").addEventListener("click", closeCartDrawer);
  document.getElementById("drawerOverlay").addEventListener("click", closeCartDrawer);

  // Checkout modal
  document.getElementById("btnProceedCheckout").addEventListener("click", openCheckoutModal);
  document.getElementById("modalCloseBtn").addEventListener("click", closeCheckoutModal);
  document.getElementById("checkoutForm").addEventListener("submit", handleCheckoutSubmit);
}

// --- CATALOG & PRODUCTS ---

async function initCategories() {
  try {
    const res = await fetch("/api/ecommerce/categories");
    if (!res.ok) return;
    const categories = await res.json();
    const bar = document.getElementById("categoriesBar");
    bar.innerHTML = `<button class="cat-chip active" onclick="selectCategory('all', this)">All Departments</button>`;
    
    categories.forEach(cat => {
      const chip = document.createElement("button");
      chip.className = "cat-chip";
      chip.textContent = cat;
      chip.onclick = () => selectCategory(cat, chip);
      bar.appendChild(chip);
    });
  } catch (err) {
    console.error("Categories fetch error:", err);
  }
}

function selectCategory(category, chipElement) {
  currentCategory = category;
  document.querySelectorAll(".cat-chip").forEach(c => c.classList.remove("active"));
  if (chipElement) chipElement.classList.add("active");
  const searchVal = document.getElementById("searchInput").value.trim();
  loadProducts(category, searchVal);
}

async function loadProducts(category = "all", search = "") {
  const grid = document.getElementById("productGrid");
  grid.innerHTML = `
    <div style="grid-column: 1 / -1; text-align: center; padding: 4rem 1rem;">
      <div style="font-size: 2rem; margin-bottom: 0.5rem; animation: spin 1s infinite linear;">⌛</div>
      <p style="color: var(--text-muted); font-weight: 600;">Streaming catalogue from Product Service & Fake Store API...</p>
    </div>
  `;

  try {
    let url = "/api/ecommerce/products?";
    if (category && category !== "all") url += `category=${encodeURIComponent(category)}&`;
    if (search) url += `search=${encodeURIComponent(search)}`;

    const res = await fetch(url);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const products = await res.json();
    allProducts = products;
    renderProducts(products);
    document.getElementById("productCount").textContent = `${products.length} products available`;
  } catch (err) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 3rem; background: #fef2f2; border: 1px solid #fecaca; border-radius: 12px;">
        <h3 style="color: #dc2626; margin-bottom: 0.5rem;">⚠️ Product Service Degradation Detected</h3>
        <p style="color: #7f1d1d; font-size: 0.9rem;">${err.message}. AIOps Sentinel telemetry is capturing this event.</p>
        <button onclick="loadProducts()" style="margin-top: 1rem; padding: 0.5rem 1rem; background: #dc2626; color: white; border: none; border-radius: 6px; cursor: pointer;">Retry Request</button>
      </div>
    `;
  }
}

function renderProducts(products) {
  const grid = document.getElementById("productGrid");
  if (!products || products.length === 0) {
    grid.innerHTML = `
      <div style="grid-column: 1 / -1; text-align: center; padding: 4rem 1rem;">
        <p style="color: var(--text-muted); font-size: 1.1rem;">No products match your search query.</p>
      </div>
    `;
    return;
  }

  grid.innerHTML = products.map(p => `
    <div class="product-card" id="product-${p.id}">
      <div class="card-image-wrap" onclick="viewProductDetail(${p.id})">
        <span class="category-tag">${p.category}</span>
        <img src="${p.image || 'https://via.placeholder.com/200'}" alt="${escapeHtml(p.title)}" loading="lazy">
      </div>
      <div class="card-body">
        <h3 class="card-title" title="${escapeHtml(p.title)}" onclick="viewProductDetail(${p.id})" style="cursor: pointer;">${escapeHtml(p.title)}</h3>
        <div class="card-rating">
          ⭐ <span>${p.rating?.rate || 4.5} (${p.rating?.count || 120} reviews)</span>
        </div>
        <div class="card-footer">
          <div class="card-price">$${p.price.toFixed(2)}</div>
          <button class="btn-add-cart" onclick="addToCart(${p.id})">
            <span>+</span> Add to Cart
          </button>
        </div>
      </div>
    </div>
  `).join("");
}

// --- CART OPERATIONS ---

async function fetchCart() {
  try {
    const res = await fetch("/api/ecommerce/cart", {
      headers: { "x-session-id": SESSION_ID }
    });
    if (!res.ok) return;
    activeCart = await res.json();
    updateCartUI();
  } catch (err) {
    console.error("Cart fetch error:", err);
  }
}

async function addToCart(productId) {
  try {
    const res = await fetch("/api/ecommerce/cart/add", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-session-id": SESSION_ID
      },
      body: JSON.stringify({ product_id: productId, quantity: 1 })
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Cart operation failed");
    }
    activeCart = await res.json();
    updateCartUI();
    showToast("Added to Cart successfully!", "success");
  } catch (err) {
    showToast(`Cart Error: ${err.message}`, "error");
  }
}

async function updateItemQty(itemId, newQty) {
  try {
    const res = await fetch(`/api/ecommerce/cart/update?item_id=${itemId}&quantity=${newQty}`, {
      method: "POST",
      headers: { "x-session-id": SESSION_ID }
    });
    if (!res.ok) throw new Error("Failed to update quantity");
    activeCart = await res.json();
    updateCartUI();
  } catch (err) {
    showToast(err.message, "error");
  }
}

async function removeCartItem(itemId) {
  try {
    const res = await fetch(`/api/ecommerce/cart/${itemId}`, {
      method: "DELETE",
      headers: { "x-session-id": SESSION_ID }
    });
    if (!res.ok) throw new Error("Failed to remove item");
    activeCart = await res.json();
    updateCartUI();
    showToast("Item removed from cart", "info");
  } catch (err) {
    showToast(err.message, "error");
  }
}

function updateCartUI() {
  const badge = document.getElementById("cartBadge");
  const count = activeCart.total_items || 0;
  badge.textContent = count;
  badge.style.display = count > 0 ? "flex" : "none";

  // Update Drawer Items
  const container = document.getElementById("drawerItems");
  const subtotalEl = document.getElementById("drawerSubtotal");
  const totalEl = document.getElementById("drawerTotal");

  if (!activeCart.items || activeCart.items.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 4rem 1rem; color: var(--text-muted);">
        <div style="font-size: 3rem; margin-bottom: 0.75rem;">🛒</div>
        <p style="font-weight: 600;">Your shopping basket is empty</p>
        <p style="font-size: 0.85rem; margin-top: 0.25rem;">Browse products to populate telemetry data.</p>
      </div>
    `;
    document.getElementById("btnProceedCheckout").disabled = true;
    document.getElementById("btnProceedCheckout").style.opacity = "0.5";
  } else {
    document.getElementById("btnProceedCheckout").disabled = false;
    document.getElementById("btnProceedCheckout").style.opacity = "1";
    container.innerHTML = activeCart.items.map(item => `
      <div class="cart-line-item">
        <img class="item-thumb" src="${item.image || 'https://via.placeholder.com/60'}" alt="${escapeHtml(item.title)}">
        <div class="item-info">
          <div class="item-title">${escapeHtml(item.title)}</div>
          <div class="item-price">$${item.price.toFixed(2)}</div>
          <div class="item-qty-controls">
            <button class="qty-btn" onclick="updateItemQty(${item.id}, ${item.quantity - 1})">-</button>
            <span style="font-size: 0.85rem; font-weight: 700;">${item.quantity}</span>
            <button class="qty-btn" onclick="updateItemQty(${item.id}, ${item.quantity + 1})">+</button>
            <button onclick="removeCartItem(${item.id})" style="background: none; border: none; color: #ef4444; font-size: 0.75rem; margin-left: auto; cursor: pointer;">Remove</button>
          </div>
        </div>
      </div>
    `).join("");
  }

  subtotalEl.textContent = `$${(activeCart.total_amount || 0).toFixed(2)}`;
  totalEl.textContent = `$${(activeCart.total_amount || 0).toFixed(2)}`;
}

function openCartDrawer() {
  document.getElementById("drawerOverlay").classList.add("open");
  document.getElementById("cartDrawer").classList.add("open");
}

function closeCartDrawer() {
  document.getElementById("drawerOverlay").classList.remove("open");
  document.getElementById("cartDrawer").classList.remove("open");
}

// --- CHECKOUT & PAYMENT FLOW ---

function openCheckoutModal() {
  closeCartDrawer();
  document.getElementById("checkoutTotal").textContent = `$${(activeCart.total_amount || 0).toFixed(2)}`;
  document.getElementById("checkoutItemsCount").textContent = `${activeCart.total_items} items`;
  document.getElementById("checkoutModal").classList.add("open");
}

function closeCheckoutModal() {
  document.getElementById("checkoutModal").classList.remove("open");
}

async function handleCheckoutSubmit(e) {
  e.preventDefault();
  const btn = document.getElementById("btnSubmitPayment");
  const spinner = document.getElementById("paySpinner");
  const btnText = document.getElementById("payBtnText");

  btn.disabled = true;
  spinner.style.display = "inline-block";
  btnText.textContent = "Authorizing with Payment Service...";

  const payload = {
    customer_name: document.getElementById("custName").value.trim(),
    customer_email: document.getElementById("custEmail").value.trim(),
    card_number: document.getElementById("cardNumber").value.replace(/\s+/g, ""),
    card_exp: document.getElementById("cardExp").value.trim(),
    card_cvv: document.getElementById("cardCvv").value.trim()
  };

  try {
    const res = await fetch("/api/ecommerce/orders/checkout", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-session-id": SESSION_ID
      },
      body: JSON.stringify(payload)
    });

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || `HTTP ${res.status}: Order Placement Error`);
    }

    // Success!
    closeCheckoutModal();
    showOrderConfirmation(data);
    fetchCart();

  } catch (err) {
    showToast(`Payment Outage: ${err.message}`, "error");
    // Show failure callout in modal
    const errNotice = document.getElementById("checkoutErrorNotice");
    if (errNotice) {
      errNotice.style.display = "block";
      errNotice.innerHTML = `
        <strong>🚨 Upstream Payment Service Error</strong>
        <p style="margin-top: 0.25rem;">${err.message}</p>
        <p style="margin-top: 0.5rem; font-size: 0.75rem;">
          💡 <strong>AIOps Sentinel Detected This:</strong> Open the <a href="/sentinel" target="_blank" style="color: #b91c1c; font-weight: 700; text-decoration: underline;">Sentinel Control Center</a> to inspect the Root Cause Analysis (RCA) and approve automated recovery!
        </p>
      `;
    }
  } finally {
    btn.disabled = false;
    spinner.style.display = "none";
    btnText.textContent = "Authorize & Place Order";
  }
}

function showOrderConfirmation(order) {
  const modal = document.getElementById("confirmationModal");
  document.getElementById("confOrderNumber").textContent = order.order_number;
  document.getElementById("confTotal").textContent = `$${order.total_amount.toFixed(2)}`;
  document.getElementById("confPaymentId").textContent = order.payment_id || "Simulated-Auth";
  modal.classList.add("open");
}

function closeConfirmationModal() {
  document.getElementById("confirmationModal").classList.remove("open");
}

// --- PRODUCT DETAILS MODAL ---

function viewProductDetail(productId) {
  const prod = allProducts.find(p => p.id === productId);
  if (!prod) return;

  const modal = document.getElementById("productDetailModal");
  document.getElementById("modalProdImage").src = prod.image || "https://via.placeholder.com/300";
  document.getElementById("modalProdTitle").textContent = prod.title;
  document.getElementById("modalProdCategory").textContent = prod.category;
  document.getElementById("modalProdPrice").textContent = `$${prod.price.toFixed(2)}`;
  document.getElementById("modalProdDesc").textContent = prod.description;
  document.getElementById("modalProdRating").textContent = `⭐ ${prod.rating?.rate || 4.5} (${prod.rating?.count || 100} ratings)`;

  const addBtn = document.getElementById("modalAddToCartBtn");
  addBtn.onclick = () => {
    addToCart(prod.id);
    closeProductDetailModal();
  };

  modal.classList.add("open");
}

function closeProductDetailModal() {
  document.getElementById("productDetailModal").classList.remove("open");
}

// --- CHAOS & FAILURE LAB QUICK BAR ---

async function pollChaosStatus() {
  try {
    const res = await fetch("/api/simulation/status");
    if (!res.ok) return;
    const data = await res.json();
    const bar = document.getElementById("chaosQuickBar");
    if (!bar) return;

    if (data.total_active > 0) {
      const names = Object.keys(data.active_scenarios).join(", ");
      bar.style.display = "flex";
      bar.innerHTML = `
        <span class="chaos-pill">⚡ CHAOS ACTIVE</span>
        <span>Injecting: <strong>${names}</strong></span>
        <a href="/sentinel" target="_blank" style="color: #38bdf8; text-decoration: underline; margin-left: 0.5rem;">View SRE Sentinel RCA →</a>
      `;
    } else {
      bar.style.display = "none";
    }
  } catch (e) {}
}

// --- UTILITY TOAST ---

function showToast(message, type = "info") {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.remove();
  }, 4000);
}

function escapeHtml(str) {
  return str ? str.replace(/[&<>'"]/g, tag => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[tag] || tag)) : "";
}
