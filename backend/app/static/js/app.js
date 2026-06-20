// ============= CONFIGURATION & ÉTAT GLOBAL =============
const CONFIG = {
    // Utilise dynamiquement le domaine actuel (localhost en local, ou onrender en ligne)
    API_BASE: window.location.origin, 
    ITEMS_PER_PAGE: 24
};

const STATE = {
    shoppingList: [],
    allProducts: [],
    filteredProducts: [],
    currentPage: 1,
    schools: [],
    schoolYears: [],
    schoolLists: [],
    selectedProductIdFromSearch: null,
    // Un seul taux de remise global (0% par défaut)
    globalDiscount: 0
};

// ============= FONCTIONS UTILITAIRES GLOBALES =============
/**
 * Détermine si un produit est un livre (remise Livres) ou une fourniture (remise Fournitures)
 */
function isBookProduct(code, type_produit) {
    if (type_produit === 1 || type_produit === 6 || type_produit === '1' || type_produit === '6') return true;
    if (code && (code.startsWith('978') || code.startsWith('979'))) return true;
    return false;
}

/**
 * Compresse et redimensionne une image directement côté client avant envoi
 * pour soulager la mémoire du backend FastAPI (limite 500 Mo Render)
 */
function compressAndResizeImage(file, maxWidth = 800, maxHeight = 800, quality = 0.75) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = (event) => {
            const img = new Image();
            img.src = event.target.result;
            img.onload = () => {
                const canvas = document.createElement('canvas');
                let width = img.width;
                let height = img.height;

                // Conservation du ratio d'aspect
                if (width > height) {
                    if (width > maxWidth) {
                        height = Math.round((height * maxWidth) / width);
                        width = maxWidth;
                    }
                } else {
                    if (height > maxHeight) {
                        width = Math.round((width * maxHeight) / height);
                        height = maxHeight;
                    }
                }

                canvas.width = width;
                canvas.height = height;

                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);

                // Export sous format JPEG compressé
                const compressedDataUrl = canvas.toDataURL('image/jpeg', quality);
                resolve(compressedDataUrl);
            };
            img.onerror = (err) => reject(err);
        };
        reader.onerror = (err) => reject(err);
    });
}

// ============= INITIALISATION DE L'APPLICATION =============
document.addEventListener('DOMContentLoaded', () => {
    console.log('🟢 Initialisation de l\'application ERP...');
    
    // Charger la liste d'achats depuis le localStorage
    loadShoppingList();
    updateCartBadge();

    // Initialiser les modules
    initNavigation();
    initProductEvents();
    initGlobalModals();
    initializeSyncSystem();

    // Premier chargement des données
    loadProducts();
});

// ============= GESTION DE LA LISTE SCOLAIRE (Shopping Cart) =============
function loadShoppingList() {
    const saved = localStorage.getItem('shoppingList');
    if (saved) {
        try {
            STATE.shoppingList = JSON.parse(saved);
        } catch (e) {
            console.error('Erreur lors de la lecture de la liste d\'achats', e);
            STATE.shoppingList = [];
        }
    }
    // Charger également la remise globale personnalisée
    const savedGlobalDiscount = localStorage.getItem('globalDiscount');
    if (savedGlobalDiscount !== null) {
        STATE.globalDiscount = parseInt(savedGlobalDiscount) || 0;
    } else {
        STATE.globalDiscount = 0; // Aucun appliqué par défaut
    }
}

function saveShoppingList() {
    localStorage.setItem('shoppingList', JSON.stringify(STATE.shoppingList));
    localStorage.setItem('globalDiscount', STATE.globalDiscount);
}

function addToShoppingList(product) {
    const existing = STATE.shoppingList.find(item => item.id === product.id);
    
    if (existing) {
        existing.qty += 1;
    } else {
        STATE.shoppingList.push({
            ...product,
            qty: 1
        });
    }
    
    saveShoppingList();
    alert(`✅ "${product.titre}" a été ajouté à la liste!`);
    updateCartBadge();
}

function updateCartBadge() {
    const badge = document.getElementById('cartBadge');
    if (badge) {
        badge.textContent = STATE.shoppingList.length;
        badge.style.display = STATE.shoppingList.length > 0 ? 'inline-flex' : 'none';
    }
}

function openShoppingListModal() {
    const existingModal = document.querySelector('.shopping-list-overlay');
    if (existingModal) existingModal.remove();

    const modal = createShoppingListModal();
    document.body.appendChild(modal);
}

function createShoppingListModal() {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay shopping-list-overlay';
    
    let itemsHTML = '';
    let subtotal = 0;
    
    STATE.shoppingList.forEach((item, index) => {
        const itemTotal = (item.prix_vente || 0) * item.qty;
        subtotal += itemTotal;
        
        const imageUrl = item.image_url || 'https://via.placeholder.com/50?text=No+Image';
        
        itemsHTML += `
            <tr>
                <td>${index + 1}</td>
                <td>
                    <img src="${imageUrl}" alt="Image" style="width: 40px; height: 60px; object-fit: cover; border-radius: 4px;">
                </td>
                <td>${item.titre || 'Sans titre'}</td>
                <td>${item.code || 'N/A'}</td>
                <td class="text-center">
                    <input type="number" class="qty-input" value="${item.qty}" min="1" data-index="${index}" style="width: 60px; padding: 5px;">
                </td>
                <td class="text-center">${itemTotal.toLocaleString('fr-FR')} FCFA</td>
                <td class="text-center">
                    <button class="btn-remove" data-index="${index}" style="background: #dc3545; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer;">❌</button>
                </td>
            </tr>
        `;
    });
    
    const discountValue = Math.round(subtotal * (STATE.globalDiscount / 100));
    const totalTtc = subtotal - discountValue;

    overlay.innerHTML = `
        <div class="modal" style="max-width: 900px;">
            <div class="modal-header">
                <h2>📚 Ma Liste Scolaire</h2>
                <button class="close-modal">&times;</button>
            </div>
            <div class="modal-body">
                <table style="width: 100%; border-collapse: collapse;">
                    <thead style="background: #001a70; color: white;">
                        <tr>
                            <th style="padding: 12px;">N°</th>
                            <th style="padding: 12px;">Image</th>
                            <th style="padding: 12px;">Désignation</th>
                            <th style="padding: 12px;">ISBN / EAN</th>
                            <th style="padding: 12px;">Quantité</th>
                            <th style="padding: 12px;">Sous-total</th>
                            <th style="padding: 12px;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${itemsHTML || '<tr><td colspan="7" style="text-align: center; padding: 20px;">Aucun produit dans la liste</td></tr>'}
                    </tbody>
                </table>
                
                ${STATE.shoppingList.length > 0 ? `
                    <div style="margin-top: 30px; text-align: right;">
                        <div style="font-size: 18px; margin-bottom: 15px;">
                            <strong>Sous-total des articles :</strong> ${subtotal.toLocaleString('fr-FR')} FCFA
                        </div>
                        
                        <!-- Configuration interactive de la remise unique du panier -->
                        <div style="display: flex; justify-content: flex-end; gap: 20px; margin-bottom: 15px; background: #f8fafc; padding: 12px; border-radius: 8px; border: 1px solid #e2e8f0; align-items: center;">
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <label style="font-size: 14px;"><strong>Pourcentage de remise globale :</strong></label>
                                <input type="number" id="cartGlobalDiscount" class="discount-input" value="${STATE.globalDiscount}" min="0" max="100" style="width: 70px; padding: 5px; text-align: center; font-weight: bold; border: 1px solid #cbd5e1; border-radius: 4px; color: #111;">
                                <span style="font-size: 14px; font-weight: bold; color: #111;">%</span>
                            </div>
                        </div>

                        <div style="font-size: 16px; margin-bottom: 15px; color: #64748b;">
                            <strong>Remise Appliquée (${STATE.globalDiscount}%) :</strong> -${discountValue.toLocaleString('fr-FR')} FCFA
                        </div>
                        
                        <div style="font-size: 24px; color: #001a70; padding: 15px; background: #f2b300; border-radius: 8px; width: fit-content; margin-left: auto;">
                            <strong>Total TTC Final:</strong> ${totalTtc.toLocaleString('fr-FR')} FCFA
                        </div>
                    </div>
                ` : ''}
            </div>
            <div class="modal-footer">
                <button class="close-modal btn btn-secondary">Fermer</button>
                ${STATE.shoppingList.length > 0 ? '<button class="btn btn-primary" id="generatePdfBtn">📄 Générer le PDF</button>' : ''}
            </div>
        </div>
    `;
    
    // Listeners internes
    overlay.querySelectorAll('.qty-input').forEach(input => {
        input.addEventListener('change', (e) => {
            const index = parseInt(e.target.dataset.index);
            const newQty = parseInt(e.target.value) || 1;
            STATE.shoppingList[index].qty = Math.max(1, newQty);
            saveShoppingList();
            openShoppingListModal();
        });
    });

    // Prise en compte des modifications de pourcentage unique
    overlay.querySelectorAll('.discount-input').forEach(input => {
        input.addEventListener('change', (e) => {
            const val = parseInt(e.target.value) || 0;
            STATE.globalDiscount = Math.max(0, Math.min(100, val));
            saveShoppingList();
            openShoppingListModal();
        });
    });
    
    overlay.querySelectorAll('.btn-remove').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const index = parseInt(e.target.dataset.index);
            STATE.shoppingList.splice(index, 1);
            saveShoppingList();
            updateCartBadge();
            openShoppingListModal();
        });
    });
    
    const pdfBtn = overlay.querySelector('#generatePdfBtn');
    if (pdfBtn) {
        pdfBtn.addEventListener('click', generateShoppingListPDF);
    }
    
    return overlay;
}

async function generateShoppingListPDF() {
    try {
        const response = await fetch(`${CONFIG.API_BASE}/generate-pdf`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                items: STATE.shoppingList,
                discount_percent: STATE.globalDiscount
            })
        });

        if (!response.ok) throw new Error('Erreur lors de la génération du PDF');

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'liste_scolaire.pdf';
        a.click();
        window.URL.revokeObjectURL(url);
        
        alert('✅ PDF généré avec succès!');
    } catch (error) {
        alert('❌ Erreur: ' + error.message);
    }
}

// ============= ÉVÉNEMENTS PRODUITS (PANEL PRINCIPAL) =============
function initProductEvents() {
    const searchBtn = document.getElementById('searchBtn');
    const searchInput = document.getElementById('searchInput');
    const viewListBtn = document.getElementById('viewListBtn');

    const toggleFiltersBtn = document.getElementById('toggleFilters');
    const filtersPanel = document.getElementById('filtersPanel');
    const applyFiltersBtn = document.getElementById('applyFilters');
    const resetFiltersBtn = document.getElementById('resetFilters');

    if (searchBtn) searchBtn.addEventListener('click', handleSearch);
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') handleSearch();
        });
    }

    if (toggleFiltersBtn && filtersPanel) {
        toggleFiltersBtn.addEventListener('click', () => {
            filtersPanel.classList.toggle('hidden');
        });
    }

    if (applyFiltersBtn) applyFiltersBtn.addEventListener('click', applyFilters);
    if (resetFiltersBtn) resetFiltersBtn.addEventListener('click', resetFilters);
    if (viewListBtn) viewListBtn.addEventListener('click', openShoppingListModal);
}

// ============= GESTION DES MODALES GLOBALISÉE =============
function initGlobalModals() {
    document.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal-overlay')) {
            e.target.remove();
        }
        if (e.target.classList.contains('close-modal')) {
            e.target.closest('.modal-overlay').remove();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.modal-overlay').forEach(modal => modal.remove());
        }
    });
}

function openDetailsModal(product) {
    const modal = createDetailsModal(product);
    document.body.appendChild(modal);
}

function createDetailsModal(product) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    
    const imageUrl = product.image_url || 'https://via.placeholder.com/300x200?text=No+Image';
    const disponibilite = product.disponibilite > 0 ? '✅ Disponible' : '❌ Indisponible';
    
    overlay.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h2>📋 Détails du Produit</h2>
                <button class="close-modal">&times;</button>
            </div>
            <div class="modal-body">
                <div class="details-container">
                    <div class="details-image" style="text-align: center; margin-bottom: 15px;">
                        <img src="${imageUrl}" alt="${product.titre}" style="max-height: 250px; object-fit: contain;" onerror="this.src='https://via.placeholder.com/300x200?text=No+Image'">
                    </div>
                    <div class="details-content">
                        <div class="detail-item"><strong>ISBN / EAN:</strong> <span>${product.code || 'N/A'}</span></div>
                        <div class="detail-item"><strong>Titre:</strong> <span>${product.titre || 'N/A'}</span></div>
                        <div class="detail-item"><strong>Prix de vente:</strong> <span>${product.prix_vente ? product.prix_vente.toLocaleString('fr-FR') : 'N/A'} FCFA</span></div>
                        <div class="detail-item"><strong>Disponibilité:</strong> <span>${disponibilite}</span></div>
                        ${product.pages ? `<div class="detail-item"><strong>Pages:</strong> <span>${product.pages}</span></div>` : ''}
                        ${product.poids ? `<div class="detail-item"><strong>Poids:</strong> <span>${product.poids}g</span></div>` : ''}
                        ${product.description ? `<div class="detail-item"><strong>Description:</strong> <span>${product.description}</span></div>` : ''}
                    </div>
                </div>
            </div>
            <div class="modal-footer">
                <button class="close-modal btn btn-secondary">Fermer</button>
            </div>
        </div>
    `;
    return overlay;
}

function openEditModal(product) {
    const modal = createEditModal(product);
    document.body.appendChild(modal);
}

function createEditModal(product) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    
    overlay.innerHTML = `
        <div class="modal modal-fullscreen">
            <div class="modal-header">
                <h2>✏️ Modifier le Produit</h2>
                <button class="close-modal">&times;</button>
            </div>
            <div class="modal-body">
                <form class="edit-form" id="editForm" data-product-id="${product.id}">
                    <div class="form-group">
                        <label>Code:</label>
                        <input type="text" name="code" value="${product.code || ''}" required>
                    </div>
                    <div class="form-group">
                        <label>Titre:</label>
                        <input type="text" name="titre" value="${product.titre || ''}" required>
                    </div>
                    <div class="form-group">
                        <label>Image:</label>
                        <div class="image-preview-container">
                            <img id="imagePreview" src="${product.image_url || 'https://via.placeholder.com/200?text=No+Image'}" alt="Aperçu" class="image-preview" style="max-height: 120px;">
                        </div>
                        <input type="file" name="image_file" id="imageFile" accept="image/*" class="image-input">
                        <input type="hidden" name="image_url" value="${product.image_url || ''}">
                        <small>Sélectionnez une image locale</small>
                    </div>
                    <div class="form-group">
                        <label>Auteurs:</label>
                        <input type="text" name="auteurs" value="${product.auteurs || ''}">
                    </div>
                    <div class="form-group">
                        <label>Éditeur:</label>
                        <input type="text" name="editeur" value="${product.editeur || ''}">
                    </div>
                    <div class="form-group">
                        <label>Collection:</label>
                        <input type="text" name="collection" value="${product.collection || ''}">
                    </div>
                    <div class="form-group">
                        <label>Prix de vente (FCFA):</label>
                        <input type="number" name="prix_vente" value="${product.prix_vente || ''}" step="0.01" required>
                    </div>
                    <div class="form-group">
                        <label>Prix catalogue (FCFA):</label>
                        <input type="number" name="prix_catalogue" value="${product.prix_catalogue || ''}" step="0.01">
                    </div>
                    <div class="form-group">
                        <label>Pages:</label>
                        <input type="number" name="pages" value="${product.pages || ''}">
                    </div>
                    <div class="form-group">
                        <label>Poids (g):</label>
                        <input type="number" name="poids" value="${product.poids || ''}" step="0.1">
                    </div>
                    <div class="form-group">
                        <label>Disponibilité:</label>
                        <select name="disponibilite">
                            <option value="1" ${product.disponibilite > 0 ? 'selected' : ''}>✅ Disponible</option>
                            <option value="0" ${product.disponibilite === 0 ? 'selected' : ''}>❌ Indisponible</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label>Description:</label>
                        <textarea name="description" rows="3">${product.description || ''}</textarea>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button class="close-modal btn btn-secondary">Annuler</button>
                <button type="button" class="btn btn-primary" id="saveBtn">💾 Enregistrer</button>
            </div>
        </div>
    `;
    
    const imageInput = overlay.querySelector('#imageFile');
    const imagePreview = overlay.querySelector('#imagePreview');
    const imageUrlInput = overlay.querySelector('input[name="image_url"]');
    
    // Optimisation : compression et redimensionnement asynchrone côté client
    imageInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (file) {
            if (!file.type.startsWith('image/')) {
                alert('⚠️ Veuillez sélectionner un fichier image valide.');
                return;
            }
            try {
                // Rétroaction visuelle pendant la compression
                imagePreview.style.opacity = '0.5';
                const compressedBase64 = await compressAndResizeImage(file, 800, 800, 0.75);
                
                imagePreview.src = compressedBase64;
                imageUrlInput.value = compressedBase64;
            } catch (err) {
                console.error('Erreur lors du traitement de l\'image :', err);
                alert('❌ Erreur lors de la compression de l\'image.');
            } finally {
                imagePreview.style.opacity = '1';
            }
        }
    });
    
    overlay.querySelector('#saveBtn').addEventListener('click', () => {
        saveProductChanges(product.id, overlay);
    });
    
    return overlay;
}

async function saveProductChanges(productId, modalOverlay) {
    const form = modalOverlay.querySelector('#editForm');
    const formData = new FormData(form);
    const data = Object.fromEntries(formData);

    const cleanData = {};
    for (const [key, value] of Object.entries(data)) {
        if (key === 'image_file' || value === '' || value === null) continue;
        
        if (['pages', 'poids', 'prix_vente', 'prix_catalogue', 'disponibilite'].includes(key)) {
            const numValue = parseFloat(value);
            if (!isNaN(numValue)) cleanData[key] = numValue;
        } else {
            cleanData[key] = value;
        }
    }

    try {
        const response = await fetch(`${CONFIG.API_BASE}/products/${productId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cleanData)
        });

        const responseData = await response.json();
        if (!response.ok) throw new Error(responseData.message || 'Erreur lors de la mise à jour');

        modalOverlay.remove();
        loadProducts();
        alert('✅ Produit mis à jour avec succès!');
    } catch (error) {
        alert('❌ Erreur: ' + error.message);
    }
}

// ============= CATALOGUE DE PRODUITS =============
async function loadProducts() {
    const loadingDiv = document.getElementById('loading');
    const errorDiv = document.getElementById('error');
    const productsContainer = document.getElementById('productsContainer');

    try {
        if (loadingDiv) loadingDiv.style.display = 'block';
        if (errorDiv) errorDiv.classList.remove('show');
        if (productsContainer) productsContainer.innerHTML = '';

        const response = await fetch(`${CONFIG.API_BASE}/products`);
        if (!response.ok) throw new Error('Erreur lors du chargement des produits');

        const data = await response.json();
        
        // Optimisation mémoire : libération explicite de l'ancienne mémoire
        STATE.allProducts = null;
        STATE.filteredProducts = null;

        STATE.allProducts = data.items || [];
        STATE.filteredProducts = [...STATE.allProducts];
        STATE.currentPage = 1;
        
        displayProducts(STATE.filteredProducts);
        updateStats();
    } catch (error) {
        showError('Erreur: ' + error.message);
    } finally {
        if (loadingDiv) loadingDiv.style.display = 'none';
    }
}

function applyFilters() {
    const minPriceInput = document.getElementById('minPrice');
    const maxPriceInput = document.getElementById('maxPrice');
    const disponibiliteFilter = document.getElementById('disponibiliteFilter');

    const minPrice = minPriceInput ? parseFloat(minPriceInput.value) || 0 : 0;
    const maxPrice = maxPriceInput ? parseFloat(maxPriceInput.value) || Infinity : Infinity;
    const disponibilite = disponibiliteFilter ? disponibiliteFilter.value : '';

    STATE.filteredProducts = STATE.allProducts.filter(product => {
        const price = product.prix_vente || 0;
        if (price < minPrice || price > maxPrice) return false;

        if (disponibilite !== '') {
            const isAvailable = product.disponibilite > 0 ? '1' : '0';
            if (isAvailable !== disponibilite) return false;
        }
        return true;
    });

    STATE.currentPage = 1;
    displayProducts(STATE.filteredProducts);
    updateStats();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

function resetFilters() {
    const searchInput = document.getElementById('searchInput');
    const minPriceInput = document.getElementById('minPrice');
    const maxPriceInput = document.getElementById('maxPrice');
    const disponibiliteFilter = document.getElementById('disponibiliteFilter');

    if (searchInput) searchInput.value = '';
    if (minPriceInput) minPriceInput.value = '';
    if (maxPriceInput) maxPriceInput.value = '';
    if (disponibiliteFilter) disponibiliteFilter.value = '';

    STATE.filteredProducts = [...STATE.allProducts];
    STATE.currentPage = 1;
    displayProducts(STATE.filteredProducts);
    updateStats();
}

function displayProducts(products) {
    const productsContainer = document.getElementById('productsContainer');
    const paginationDiv = document.getElementById('pagination');
    if (!productsContainer) return;

    productsContainer.innerHTML = '';

    if (products.length === 0) {
        productsContainer.innerHTML = '<p style="grid-column: 1/-1; text-align: center; color: white; padding: 40px;">Aucun produit trouvé</p>';
        if (paginationDiv) paginationDiv.innerHTML = '';
        return;
    }

    const totalPages = Math.ceil(products.length / CONFIG.ITEMS_PER_PAGE);
    const startIndex = (STATE.currentPage - 1) * CONFIG.ITEMS_PER_PAGE;
    const endIndex = startIndex + CONFIG.ITEMS_PER_PAGE;
    const pageProducts = products.slice(startIndex, endIndex);

    pageProducts.forEach(product => {
        const card = createProductCard(product);
        productsContainer.appendChild(card);
    });

    displayPagination(totalPages);
}

function createProductCard(product) {
    const card = document.createElement('div');
    card.className = 'product-card';
    
    const imageUrl = product.image_url || 'https://via.placeholder.com/300x200?text=No+Image';
    const title = product.titre || 'Sans titre';
    const price = product.prix_vente ? product.prix_vente.toLocaleString('fr-FR') : 'N/A';
    const disponibilite = product.disponibilite > 0 ? '✅ Disponible' : '❌ Indisponible';

    card.innerHTML = `
        <div class="product-image">
            <img src="${imageUrl}" alt="${title}" onerror="this.src='https://via.placeholder.com/300x200?text=No+Image'">
        </div>
        <div class="product-info">
            <div class="product-code">${product.code || 'N/A'}</div>
            <div class="product-title">${title}</div>
            <div class="product-meta">
                ${product.pages ? `📄 ${product.pages} pages<br>` : ''}
                ${product.poids ? `⚖️ ${product.poids}g<br>` : ''}
                ${disponibilite}
            </div>
            <div class="product-price">${price} FCFA</div>
            <div class="product-actions">
                <button class="btn btn-add-to-list">🛒 Ajouter à la liste</button>
                <button class="btn btn-details">👁️ Détails</button>
                <button class="btn btn-edit">✏️ Modifier</button>
            </div>
        </div>
    `;

    card.querySelector('.btn-add-to-list').addEventListener('click', () => addToShoppingList(product));
    card.querySelector('.btn-details').addEventListener('click', () => openDetailsModal(product));
    card.querySelector('.btn-edit').addEventListener('click', () => openEditModal(product));

    return card;
}

function displayPagination(totalPages) {
    const paginationDiv = document.getElementById('pagination');
    if (!paginationDiv) return;

    paginationDiv.innerHTML = '';
    if (totalPages <= 1) return;

    if (STATE.currentPage > 1) {
        const prevBtn = document.createElement('button');
        prevBtn.textContent = '← Précédent';
        prevBtn.addEventListener('click', () => {
            STATE.currentPage--;
            displayProducts(STATE.filteredProducts);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
        paginationDiv.appendChild(prevBtn);
    }

    for (let i = 1; i <= totalPages; i++) {
        if (i <= 10 || i === totalPages) {
            const btn = document.createElement('button');
            btn.textContent = i;
            btn.className = i === STATE.currentPage ? 'active' : '';
            btn.addEventListener('click', () => {
                STATE.currentPage = i;
                displayProducts(STATE.filteredProducts);
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
            paginationDiv.appendChild(btn);
        }

        if (i === 10 && totalPages > 11) {
            const dots = document.createElement('span');
            dots.textContent = '...';
            dots.className = 'pagination-dots';
            paginationDiv.appendChild(dots);
        }
    }

    if (STATE.currentPage < totalPages) {
        const nextBtn = document.createElement('button');
        nextBtn.textContent = 'Suivant →';
        nextBtn.addEventListener('click', () => {
            STATE.currentPage++;
            displayProducts(STATE.filteredProducts);
            window.scrollTo({ top: 0, behavior: 'smooth' });
        });
        paginationDiv.appendChild(nextBtn);
    }
}

function handleSearch() {
    const searchInput = document.getElementById('searchInput');
    if (!searchInput) return;

    const query = searchInput.value.toLowerCase().trim();

    if (!query) {
        STATE.filteredProducts = [...STATE.allProducts];
    } else {
        STATE.filteredProducts = STATE.allProducts.filter(product => 
            (product.code && product.code.toLowerCase().includes(query)) ||
            (product.titre && product.titre.toLowerCase().includes(query))
        );
    }

    STATE.currentPage = 1;
    displayProducts(STATE.filteredProducts);
    updateStats();
}

function updateStats() {
    const statsText = document.getElementById('statsText');
    if (!statsText) return;

    const total = STATE.allProducts.length;
    const shown = STATE.filteredProducts.length;
    const available = STATE.filteredProducts.filter(p => p.disponibilite > 0).length;
    
    statsText.textContent = `📊 ${shown}/${total} produits affichés | ✅ ${available} disponibles`;
}

function showError(message) {
    const errorDiv = document.getElementById('error');
    if (errorDiv) {
        errorDiv.textContent = message;
        errorDiv.classList.add('show');
    }
}

// ============= SYNC MANAGEMENT =============
function initializeSyncSystem() {
    console.log('🔄 Initialisation du système de sync...');
    
    const syncBtn = document.getElementById('syncBtn');
    const stopSyncBtn = document.getElementById('stopSyncBtn');
    const syncProgress = document.getElementById('syncProgress');
    const progressFill = document.getElementById('progressFill');
    const syncMessage = document.getElementById('syncMessage');
    const syncModal = document.getElementById('syncModal');
    const syncModalContent = document.getElementById('syncModalContent');
    const modalProgressFill = document.getElementById('modalProgressFill');
    const syncLogs = document.getElementById('syncLogs');

    if (!syncBtn || !syncModal) {
        console.warn('⚠️ Éléments de synchronisation manquants dans le DOM');
        return;
    }

    syncBtn.addEventListener('click', async function() {
        syncBtn.disabled = true;
        if (stopSyncBtn) stopSyncBtn.classList.remove('hidden');
        if (syncProgress) syncProgress.classList.remove('hidden');
        if (syncMessage) syncMessage.textContent = 'Démarrage de la synchronisation...';
        if (progressFill) {
            progressFill.style.width = '0%';
            progressFill.textContent = '0%';
        }
        syncModal.classList.remove('hidden');
        if (syncModalContent) {
            syncModalContent.style.transform = 'translate(-50%, -50%)';
            syncModalContent.style.left = '50%';
            syncModalContent.style.top = '50%';
        }
        if (modalProgressFill) {
            modalProgressFill.style.width = '0%';
            modalProgressFill.textContent = '0%';
        }
        if (syncLogs) syncLogs.innerHTML = '';

        try {
            const response = await fetch(`${CONFIG.API_BASE}/sync/start`, { method: 'POST' });
            if (!response.ok) throw new Error('HTTP ' + response.status);
            checkSyncProgress();
        } catch (error) {
            console.error('❌ Erreur de synchro:', error);
            if (syncMessage) syncMessage.textContent = '❌ Erreur: ' + error.message;
            syncBtn.disabled = false;
            if (syncProgress) syncProgress.classList.add('hidden');
            syncModal.classList.add('hidden');
        }
    });

    const stopAction = async () => {
        try {
            await fetch(`${CONFIG.API_BASE}/sync/stop`, { method: 'POST' });
            syncBtn.disabled = false;
        } catch (e) {
            console.error(e);
        }
    };

    if (stopSyncBtn) stopSyncBtn.addEventListener('click', stopAction);
    const stopSyncBtnModal = document.getElementById('stopSyncBtnModal');
    if (stopSyncBtnModal) stopSyncBtnModal.addEventListener('click', stopAction);

    // Modal Drag and Drop
    const header = document.querySelector('.sync-modal-header');
    if (header && syncModalContent) {
        let isDragging = false;
        let initialX, initialY;

        header.addEventListener('mousedown', (e) => {
            isDragging = true;
            initialX = e.clientX - syncModalContent.offsetLeft;
            initialY = e.clientY - syncModalContent.offsetTop;
        });

        document.addEventListener('mousemove', (e) => {
            if (isDragging) {
                syncModalContent.style.left = (e.clientX - initialX) + 'px';
                syncModalContent.style.top = (e.clientY - initialY) + 'px';
                syncModalContent.style.transform = 'none';
            }
        });

        document.addEventListener('mouseup', () => { isDragging = false; });
    }

    const minimizeBtn = document.getElementById('minimizeModal');
    if (minimizeBtn && syncModalContent) {
        minimizeBtn.addEventListener('click', () => {
            syncModalContent.classList.toggle('minimized');
        });
    }

    const closeModal = document.getElementById('closeModal');
    if (closeModal) {
        closeModal.addEventListener('click', () => {
            if (confirm('Êtes-vous sûr de vouloir arrêter la synchronisation ?')) {
                stopAction();
                syncModal.classList.add('hidden');
            }
        });
    }
}

async function checkSyncProgress() {
    try {
        const response = await fetch(`${CONFIG.API_BASE}/sync/status`);
        const data = await response.json();
        if (!data.stats) return;

        const progressFill = document.getElementById('progressFill');
        const syncMessage = document.getElementById('syncMessage');
        const modalProgressFill = document.getElementById('modalProgressFill');
        const syncLogs = document.getElementById('syncLogs');

        const progressPercent = `${Math.round(data.progress)}%`;

        if (progressFill) {
            progressFill.style.width = progressPercent;
            progressFill.textContent = progressPercent;
        }
        if (syncMessage) syncMessage.textContent = data.message;
        if (modalProgressFill) {
            modalProgressFill.style.width = progressPercent;
            modalProgressFill.textContent = progressPercent;
        }

        const syncTotal = document.getElementById('syncTotal');
        const syncSuccess = document.getElementById('syncSuccess');
        const syncFailed = document.getElementById('syncFailed');
        const syncRemaining = document.getElementById('syncRemaining');
        const modalSyncMessage = document.getElementById('modalSyncMessage');
        const currentProduct = document.getElementById('currentProduct');

        if (syncTotal) syncTotal.textContent = data.stats.total;
        if (syncSuccess) syncSuccess.textContent = data.stats.success;
        if (syncFailed) syncFailed.textContent = data.stats.failed;
        if (syncRemaining) syncRemaining.textContent = data.stats.pending;
        if (modalSyncMessage) modalSyncMessage.textContent = data.message;
        if (currentProduct) currentProduct.textContent = `Article en cours : ${data.stats.current_product || '-'}`;

        if (syncLogs && data.stats.logs && data.stats.logs.length > 0) {
            syncLogs.innerHTML = data.stats.logs
                .slice(-50)
                .map(line => `<div>${escapeHtml(line)}</div>`)
                .join('');
            syncLogs.scrollTop = syncLogs.scrollHeight;
        }

        if (data.running) {
            setTimeout(checkSyncProgress, 2000);
        } else {
            const syncBtn = document.getElementById('syncBtn');
            const syncProgress = document.getElementById('syncProgress');
            const syncModal = document.getElementById('syncModal');
            const stopSyncBtn = document.getElementById('stopSyncBtn');

            if (syncBtn) syncBtn.disabled = false;
            if (stopSyncBtn) stopSyncBtn.classList.add('hidden');

            setTimeout(() => {
                if (syncProgress) syncProgress.classList.add('hidden');
                if (syncModal) syncModal.classList.add('hidden');
                loadProducts();
            }, 2000);
        }
    } catch (error) {
        console.error('❌ Erreur checkSyncProgress:', error);
    }
}

function escapeHtml(text) {
    const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

// ============= SYSTEME DE NAVIGATION DE LA SPA =============
function initNavigation() {
    const navContainer = document.getElementById('sidebar-nav');
    if (!navContainer) return;

    navContainer.addEventListener('click', (e) => {
        const btn = e.target.closest('.nav-btn');
        if (!btn) return;

        const targetPage = btn.dataset.target;
        if (!targetPage) return;

        // Gérer les classes actives sur les boutons
        navContainer.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');

        // Gérer l'affichage des sections
        document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
        const targetSection = document.getElementById('page-' + targetPage);
        if (targetSection) targetSection.classList.remove('hidden');

        // Charger les données de la page correspondante
        switch (targetPage) {
            case 'lists':
                loadSchoolsForLists();
                break;
            case 'schools':
                loadSchools();
                break;
            case 'years':
                loadYears();
                break;
        }
    });

    // Lier le bouton "Nouvelle Liste" de l'en-tête (page Listes)
    const createListBtn = document.getElementById('createListBtn');
    if (createListBtn) {
        createListBtn.addEventListener('click', openCreateListModal);
    }
}

// ============= ÉCOLES (SCHOOLS MODULE) =============
async function loadSchools() {
    const container = document.getElementById('schoolsContainer');
    if (!container) return;

    try {
        const res = await fetch(`${CONFIG.API_BASE}/schools`);
        const data = await res.json();
        STATE.schools = data;

        container.innerHTML = `
            <div style="margin-bottom: 20px;">
                <button class="btn btn-primary" id="addSchoolBtn">➕ Ajouter une école</button>
            </div>
            <div class="cards-grid">
                ${data.map(school => `
                    <div class="card">
                        <h3>🏫 ${school.nom}</h3>
                        <p><strong>Ville:</strong> ${school.ville || 'N/A'}</p>
                        <p><strong>Statut:</strong> ${school.actif === 1 ? '✅ Active' : '❌ Inactive'}</p>
                        <div class="card-actions">
                            <button class="btn btn-primary btn-sm btn-edit-school" data-id="${school.id}" data-nom="${school.nom}" data-ville="${school.ville || ''}">✏️ Modifier</button>
                            <button class="btn btn-danger btn-sm btn-delete-school" data-id="${school.id}">🗑️ Supprimer</button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        // Événements dynamiques
        container.querySelector('#addSchoolBtn').addEventListener('click', openCreateSchoolModal);
        container.querySelectorAll('.btn-edit-school').forEach(btn => {
            btn.addEventListener('click', () => openEditSchoolModal(btn.dataset.id, btn.dataset.nom, btn.dataset.ville));
        });
        container.querySelectorAll('.btn-delete-school').forEach(btn => {
            btn.addEventListener('click', () => deleteSchool(btn.dataset.id));
        });

    } catch (error) {
        console.error('Erreur:', error);
        container.innerHTML = '<p style="color: red;">Erreur lors du chargement des écoles</p>';
    }
}

function openCreateSchoolModal() {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h2>➕ Ajouter une école</h2>
                <button class="close-modal">&times;</button>
            </div>
            <div class="modal-body">
                <form id="schoolForm" style="max-width: 600px;">
                    <div class="form-group">
                        <label>Nom de l'établissement:</label>
                        <input type="text" id="schoolName" placeholder="Ex: Lycée Blaise Pascal" required>
                    </div>
                    <div class="form-group">
                        <label>Ville:</label>
                        <input type="text" id="schoolCity" placeholder="Ex: Libreville">
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button class="close-modal btn btn-secondary">Annuler</button>
                <button class="btn btn-primary" id="saveNewSchoolBtn">💾 Enregistrer</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('#saveNewSchoolBtn').addEventListener('click', saveSchool);
}

function openEditSchoolModal(id, nom, ville) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h2>✏️ Modifier l'école</h2>
                <button class="close-modal">&times;</button>
            </div>
            <div class="modal-body">
                <form id="editSchoolForm" style="max-width: 600px;">
                    <div class="form-group">
                        <label>Nom de l'établissement:</label>
                        <input type="text" id="editSchoolName" value="${nom}" required>
                    </div>
                    <div class="form-group">
                        <label>Ville:</label>
                        <input type="text" id="editSchoolCity" value="${ville}">
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button class="close-modal btn btn-secondary">Annuler</button>
                <button class="btn btn-primary" id="updateSchoolBtn">💾 Enregistrer</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('#updateSchoolBtn').addEventListener('click', () => updateSchool(id));
}

async function saveSchool() {
    const name = document.getElementById('schoolName').value.trim();
    const city = document.getElementById('schoolCity').value.trim();

    if (!name) {
        alert('⚠️ Le nom de l\'école est obligatoire');
        return;
    }

    try {
        const res = await fetch(`${CONFIG.API_BASE}/schools`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nom: name, ville: city })
        });

        if (!res.ok) throw new Error('Erreur lors de la création');

        alert('✅ École ajoutée avec succès!');
        document.querySelector('.modal-overlay').remove();
        loadSchools();
    } catch (error) {
        alert('❌ Erreur: ' + error.message);
    }
}

async function updateSchool(id) {
    const name = document.getElementById('editSchoolName').value.trim();
    const city = document.getElementById('editSchoolCity').value.trim();

    if (!name) {
        alert('⚠️ Le nom de l\'école est obligatoire');
        return;
    }

    try {
        const res = await fetch(`${CONFIG.API_BASE}/schools/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ nom: name, ville: city })
        });

        if (!res.ok) throw new Error('Erreur de modification');

        alert('✅ École mise à jour!');
        document.querySelector('.modal-overlay').remove();
        loadSchools();
    } catch (error) {
        alert('❌ Erreur: ' + error.message);
    }
}

async function deleteSchool(id) {
    if (confirm('Êtes-vous sûr de vouloir supprimer cette école ?')) {
        try {
            const res = await fetch(`${CONFIG.API_BASE}/schools/${id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Erreur de suppression');
            alert('✅ École supprimée!');
            loadSchools();
        } catch (error) {
            alert('❌ Erreur: ' + error.message);
        }
    }
}

// ============= ANNÉES SCOLAIRES (YEARS MODULE) =============
async function loadYears() {
    const container = document.getElementById('yearsContainer');
    if (!container) return;

    try {
        const res = await fetch(`${CONFIG.API_BASE}/school-years`);
        const data = await res.json();
        STATE.schoolYears = data;

        container.innerHTML = `
            <div style="margin-bottom: 20px;">
                <button class="btn btn-primary" id="addYearBtn">➕ Ajouter une année</button>
            </div>
            <div class="cards-grid">
                ${data.map(year => `
                    <div class="card">
                        <h3>📅 ${year.libelle}</h3>
                        <div class="card-actions">
                            <button class="btn btn-primary btn-sm btn-edit-year" data-id="${year.id}" data-libelle="${year.libelle}">✏️ Modifier</button>
                            <button class="btn btn-danger btn-sm btn-delete-year" data-id="${year.id}">🗑️ Supprimer</button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        container.querySelector('#addYearBtn').addEventListener('click', openCreateYearModal);
        container.querySelectorAll('.btn-edit-year').forEach(btn => {
            btn.addEventListener('click', () => openEditYearModal(btn.dataset.id, btn.dataset.libelle));
        });
        container.querySelectorAll('.btn-delete-year').forEach(btn => {
            btn.addEventListener('click', () => deleteYear(btn.dataset.id));
        });

    } catch (error) {
        console.error(error);
        container.innerHTML = '<p style="color: red;">Erreur de chargement des années</p>';
    }
}

function openCreateYearModal() {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h2>➕ Ajouter une année scolaire</h2>
                <button class="close-modal">&times;</button>
            </div>
            <div class="modal-body">
                <form id="yearForm" style="max-width: 600px;">
                    <div class="form-group">
                        <label>Année scolaire:</label>
                        <input type="text" id="yearLabel" placeholder="Ex: 2026-2027" required>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button class="close-modal btn btn-secondary">Annuler</button>
                <button class="btn btn-primary" id="saveNewYearBtn">💾 Enregistrer</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('#saveNewYearBtn').addEventListener('click', saveYear);
}

function openEditYearModal(id, label) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
        <div class="modal">
            <div class="modal-header">
                <h2>✏️ Modifier l'année scolaire</h2>
                <button class="close-modal">&times;</button>
            </div>
            <div class="modal-body">
                <form id="editYearForm" style="max-width: 600px;">
                    <div class="form-group">
                        <label>Année scolaire:</label>
                        <input type="text" id="editYearLabel" value="${label}" required>
                    </div>
                </form>
            </div>
            <div class="modal-footer">
                <button class="close-modal btn btn-secondary">Annuler</button>
                <button class="btn btn-primary" id="updateYearBtn">💾 Enregistrer</button>
            </div>
        </div>
    `;
    document.body.appendChild(overlay);
    overlay.querySelector('#updateYearBtn').addEventListener('click', () => updateYear(id));
}

async function saveYear() {
    const label = document.getElementById('yearLabel').value.trim();
    if (!label) {
        alert('⚠️ L\'année scolaire est obligatoire');
        return;
    }

    try {
        const res = await fetch(`${CONFIG.API_BASE}/school-years`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ libelle: label })
        });
        if (!res.ok) throw new Error('Erreur de création');
        alert('✅ Année ajoutée !');
        document.querySelector('.modal-overlay').remove();
        loadYears();
    } catch (error) {
        alert('❌ Erreur: ' + error.message);
    }
}

async function updateYear(id) {
    const label = document.getElementById('editYearLabel').value.trim();
    if (!label) {
        alert('⚠️ L\'année scolaire est obligatoire');
        return;
    }

    try {
        const res = await fetch(`${CONFIG.API_BASE}/school-years/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ libelle: label })
        });
        if (!res.ok) throw new Error('Erreur de mise à jour');
        alert('✅ Année modifiée !');
        document.querySelector('.modal-overlay').remove();
        loadYears();
    } catch (error) {
        alert('❌ Erreur: ' + error.message);
    }
}

async function deleteYear(id) {
    if (confirm('Êtes-vous sûr de vouloir supprimer cette année ?')) {
        try {
            const res = await fetch(`${CONFIG.API_BASE}/school-years/${id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Erreur');
            alert('✅ Année supprimée !');
            loadYears();
        } catch (error) {
            alert('❌ Erreur: ' + error.message);
        }
    }
}

// ============= LISTES SCOLAIRES (LISTS MODULE) =============
async function loadSchoolsForLists() {
    const container = document.getElementById('listsContainer');
    if (!container) return;

    try {
        const res = await fetch(`${CONFIG.API_BASE}/schools`);
        const schoolsData = await res.json();

        container.innerHTML = `
            <div style="margin-bottom: 20px;">
                <button class="btn btn-primary" id="nestedCreateListBtn">➕ Nouvelle liste</button>
            </div>

            <div class="school-selector">
                <label><strong>Sélectionnez une école:</strong></label>
                <select id="schoolSelect" style="padding: 8px; font-size: 14px; border-radius: 4px;">
                    <option value="">-- Choisir une école --</option>
                    ${schoolsData.map(school => `<option value="${school.id}">${school.nom}</option>`).join('')}
                </select>
            </div>

            <div id="listsContent"></div>
        `;

        container.querySelector('#nestedCreateListBtn').addEventListener('click', openCreateListModal);
        
        const schoolSelect = container.querySelector('#schoolSelect');
        schoolSelect.addEventListener('change', loadYearsForLists);

    } catch (error) {
        console.error('Erreur:', error);
        container.innerHTML = '<p style="color: red;">Erreur lors du chargement des écoles.</p>';
    }
}

async function loadYearsForLists() {
    const schoolId = document.getElementById('schoolSelect').value;
    const listsContent = document.getElementById('listsContent');

    if (!schoolId) {
        if (listsContent) listsContent.innerHTML = '';
        return;
    }

    try {
        const res = await fetch(`${CONFIG.API_BASE}/public/school-lists/schools/${schoolId}/years`);
        const data = await res.json();

        // ✅ Utilisation de la classe 'school-selector' pour appliquer le thème CSS sombre
        listsContent.innerHTML = `
            <div class="school-selector" style="margin-top: 20px;">
                <label><strong>Sélectionnez une année:</strong></label>
                <select id="yearSelectLists">
                    <option value="">-- Choisir une année --</option>
                    ${data.map(year => `<option value="${year.id}">${year.libelle}</option>`).join('')}
                </select>
            </div>
            <div id="classesContent"></div>
        `;

        const yearSelect = document.getElementById('yearSelectLists');
        yearSelect.addEventListener('change', (e) => loadClassesForLists(schoolId, e.target.value));

    } catch (error) {
        console.error(error);
        listsContent.innerHTML = '<p style="color: red;">Erreur de chargement des années pour cette école.</p>';
    }
}

async function loadClassesForLists(schoolId, yearId) {
    const classesContent = document.getElementById('classesContent');
    if (!yearId) {
        if (classesContent) classesContent.innerHTML = '';
        return;
    }

    try {
        const res = await fetch(`${CONFIG.API_BASE}/public/school-lists/schools/${schoolId}/years/${yearId}/classes`);
        const data = await res.json();

        classesContent.innerHTML = `
            <div class="cards-grid" style="margin-top: 20px;">
                ${data.map(list => `
                    <div class="card">
                        <h3>📚 ${list.classe}</h3>
                        <p><strong>Titre:</strong> ${list.titre || 'N/A'}</p>
                        <div class="card-actions">
                            <button class="btn btn-primary btn-sm btn-view-list" data-id="${list.id}">👁️ Voir</button>
                            <button class="btn btn-info btn-sm btn-items-list" data-id="${list.id}">📝 Articles</button>
                            <button class="btn btn-warning btn-sm btn-pdf-list" data-id="${list.id}">📄 PDF</button>
                            <button class="btn btn-success btn-sm btn-edit-list" data-id="${list.id}">✏️ Modifier</button>
                            <!-- NOUVEAU BOUTON DE DUPLICATION -->
                            <button class="btn btn-secondary btn-sm btn-duplicate-list" data-id="${list.id}">📋 Dupliquer</button>
                            <button class="btn btn-danger btn-sm btn-delete-list" data-id="${list.id}">🗑️ Supprimer</button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        // Événements dynamiques
        classesContent.querySelectorAll('.btn-view-list').forEach(b => b.addEventListener('click', () => openListDetails(b.dataset.id)));
        classesContent.querySelectorAll('.btn-items-list').forEach(b => b.addEventListener('click', () => openListItemsModal(b.dataset.id)));
        classesContent.querySelectorAll('.btn-pdf-list').forEach(b => b.addEventListener('click', () => generateListPDF(b.dataset.id)));
        classesContent.querySelectorAll('.btn-edit-list').forEach(b => b.addEventListener('click', () => openEditListModal(b.dataset.id)));
        classesContent.querySelectorAll('.btn-delete-list').forEach(b => b.addEventListener('click', () => deleteList(b.dataset.id, schoolId, yearId)));
        
        // Liaison de l'événement de duplication
        classesContent.querySelectorAll('.btn-duplicate-list').forEach(b => {
            b.addEventListener('click', () => {
                openDuplicateListModal(b.dataset.id, schoolId, yearId);
            });
        });

    } catch (error) {
        console.error(error);
        classesContent.innerHTML = '<p style="color: red;">Erreur lors du chargement des classes.</p>';
    }
}

async function openListDetails(id) {
    try {
        const res = await fetch(`${CONFIG.API_BASE}/school-lists/${id}/details`);
        const data = await res.json();

        // Récupérer le nom de l'école sélectionnée de manière sécurisée
        const schoolName = document.getElementById('schoolSelect') 
            ? document.getElementById('schoolSelect').options[document.getElementById('schoolSelect').selectedIndex].text 
            : "Établissement";

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';

        let subtotal = 0;
        let itemsHTML = '';

        (data.items || []).forEach((item, idx) => {
            const itemTotal = (item.prix_unitaire || 0) * (item.quantite || 1); // ✅ Calcul du total de la ligne
            subtotal += itemTotal;

            itemsHTML += `
            <tr>
                <td class="center"><div class="line-number">${idx + 1}</div></td>
                <td class="center">
                    <img class="book-image" src="${item.image_url || 'https://via.placeholder.com/90x120'}" alt="${item.titre || ''}" onerror="this.src='https://via.placeholder.com/90x120'">
                </td>
                <td>
                    <strong style="color: #001a70; font-size: 15px;">${item.titre || 'N/A'}</strong>
                </td>
                <td class="center" style="font-family: monospace; font-size: 14px;">${item.code || 'N/A'}</td>
                <td class="center">${item.quantite || 1}</td>
                <td class="center price">${itemTotal.toLocaleString('fr-FR')}</td>
                <td class="center barcode">${item.code || 'N/A'}</td>
            </tr>
            `;
        });

        // Calculs basés sur le pourcentage unique défini dans STATE (0% par défaut)
        const discountValue = Math.round(subtotal * (STATE.globalDiscount / 100));
        const totalTtc = subtotal - discountValue;

        overlay.innerHTML = `
        <div class="modal modal-fullscreen">
            <div class="modal-header">
                <h2>📋 Liste scolaire valorisée (Aperçu)</h2>
                <button class="close-modal">&times;</button>
            </div>
            <div class="modal-body" style="background:#eef2fb; padding: 25px;">
                
                <!-- MAQUETTE DE PREVIEW PHYSIQUE -->
                <div class="page-list-details">
                    
                    <!-- HEADER -->
                    <div class="header">
                        <div class="logo-zone">
                            <div class="logo-text">
                                <h1>Maison de<br>la Presse<br><span>Gabon</span></h1>
                                <p>Lire, apprendre, réussir !</p>
                            </div>
                        </div>
                        <div class="contact-zone">
                            <div class="contact-block">
                                📞 011 72 21 31<br>
                                📞 011 77 26 95<br>
                                🟢 WhatsApp : 066 956 027<br>
                                ✉️ ipc369@yahoo.fr<br>
                                🌐 www.maisondelapressegabon.com
                            </div>
                            <div class="shop-box">
                                2 MAGASINS<br><br>
                                📍 GLASS<br>
                                📍 OKALA
                            </div>
                        </div>
                    </div>

                    <!-- TOP BAR -->
                    <div class="top-bar">
                        <div>📋 LISTE VALORISÉE</div>
                        <div>🛡️ ENGAGEMENTS</div>
                        <div>🎁 COUVERTURE GRATUITE</div>
                    </div>

                    <!-- TITLE -->
                    <div class="title-section">
                        <div class="title-left">
                            <div class="main-title">
                                LISTE SCOLAIRE<br>
                                <span>VALORISÉE</span>
                            </div>
                        </div>
                        <div class="class-box">
                            ${data.classe.toUpperCase()}<br>
                            <span style="font-size: 12px; font-weight: normal; color: #cbd5e1;">${schoolName.toUpperCase()}</span>
                        </div>
                    </div>

                    <!-- CLIENT -->
                    <div class="client-box">
                        <div class="client-title">CLIENT</div>
                        <div class="client-grid">
                            <div>Nom & prénom : _______________________</div>
                            <div>Tél (WhatsApp) : _______________________</div>
                            <div>Classe : ${data.classe}</div>
                            <div>Observations : _______________________</div>
                        </div>
                    </div>

                    <!-- TABLE -->
                    <div class="table-wrapper">
                        <table class="maquette-table">
                            <thead>
                                <tr>
                                    <th>N°</th>
                                    <th>VISUEL</th>
                                    <th style="text-align: left;">DÉSIGNATION</th>
                                    <th>ISBN / EAN</th>
                                    <th>QTÉ</th>
                                    <th>PRIX DE VENTE</th>
                                    <th>CODE BARRE</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${itemsHTML || '<tr><td colspan="7" style="text-align:center; padding: 15px;">Aucun produit dans la liste</td></tr>'}
                            </tbody>
                        </table>
                    </div>

                    <!-- OCCASION -->
                    <div class="occase-row">
                        <div class="occase-box">📚 LIVRES SCOLAIRES D’OCCASION</div>
                        <div class="occase-box">🌱 Donnez une seconde vie aux livres</div>
                    </div>

                    <!-- TOTAL (MAQUETTE MISE À JOUR AVEC UN SEUL SÉLECTEUR DE REMISE GLOBALE) -->
                    <div class="total-wrapper">
                        <div class="total-box" style="width: 440px; border-radius: 12px; overflow: hidden; border: 2px solid #d8def0;">
                            <div class="total-line total-blue" style="display: flex; justify-content: space-between; padding: 12px 20px; font-size: 14px; font-weight: bold; background: #001a70; color: white;">
                                <span>TOTAL AVANT REMISE</span>
                                <span>${subtotal.toLocaleString('fr-FR')} FCFA</span>
                            </div>
                            <div class="total-line total-yellow" style="display: flex; justify-content: space-between; padding: 12px 20px; font-size: 14px; font-weight: bold; background: #fef08a; color: #854d0e;">
                                <span>REMISE GLOBALE ${STATE.globalDiscount}%</span>
                                <span>- ${discountValue.toLocaleString('fr-FR')} FCFA</span>
                            </div>
                            <div class="total-line total-blue" style="display: flex; justify-content: space-between; padding: 12px 20px; font-size: 15px; font-weight: bold; background: #f2b300; color: #111;">
                                <span>TOTAL TTC FINAL</span>
                                <span>${totalTtc.toLocaleString('fr-FR')} FCFA</span>
                            </div>
                        </div>
                    </div>

                    <!-- PAYMENT -->
                    <div class="payment-row">
                        <div class="payment-box">
                            MOYENS DE PAIEMENT ACCEPTÉS<br><br>
                            <div class="airtel">M4010</div>
                        </div>
                        <div class="payment-box" style="height: 90px; display: flex; align-items: center; justify-content: center;">
                            PAIEMENT SÉCURISÉ<br>
                            www.maisondelapressegabonairtel.com
                        </div>
                        <div class="payment-box" style="height: 90px; display: flex; align-items: center; justify-content: center;">
                            Conditions générales de ventes disponibles en magasin
                        </div>
                    </div>

                    <!-- FOOTER -->
                    <div class="footer">
                        <div>La Maison de la Presse Gabon, partenaire privilégié de la réussite scolaire.</div>
                        <div>Ce document est une liste valorisée et non un devis.</div>
                    </div>

                </div>
            </div>
            <div class="modal-footer">
                <button class="close-modal btn btn-secondary">Fermer</button>
            </div>
        </div>
        `;
        document.body.appendChild(overlay);
    } catch (error) {
        alert('❌ Erreur de chargement: ' + error.message);
    }
}

async function openCreateListModal() {
    const schoolSelect = document.getElementById('schoolSelect');
    const schoolId = schoolSelect ? schoolSelect.value : null;
    
    if (!schoolId) {
        alert('⚠️ Veuillez d\'abord sélectionner une école dans l\'onglet Listes');
        return;
    }

    try {
        const yearsRes = await fetch(`${CONFIG.API_BASE}/school-years`);
        const years = await yearsRes.json();

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal">
                <div class="modal-header">
                    <h2>➕ Nouvelle Liste Scolaire</h2>
                    <button class="close-modal">&times;</button>
                </div>
                <div class="modal-body">
                    <form id="createListForm" style="max-width: 600px;">
                        <div class="form-group">
                            <label>Année scolaire:</label>
                            <select id="yearSelect" required style="padding: 8px; width: 100%;">
                                <option value="">-- Choisir une année --</option>
                                ${years.map(y => `<option value="${y.id}" data-libelle="${y.libelle}">${y.libelle}</option>`).join('')}
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Classe:</label>
                            <input type="text" id="classInput" placeholder="Ex: 6ème A" required>
                        </div>
                        <div class="form-group">
                            <label>Titre (optionnel):</label>
                            <input type="text" id="titleInput" placeholder="Ex: Liste de fournitures 6ème">
                        </div>
                        <div class="form-group">
                            <label>Slug:</label>
                            <input type="text" id="slugInput" placeholder="Auto-généré" readonly style="background: #f5f5f5; width: 100%;">
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button class="close-modal btn btn-secondary">Annuler</button>
                    <button class="btn btn-primary" id="submitNewListBtn">💾 Créer la liste</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        const classInput = overlay.querySelector('#classInput');
        const yearSelect = overlay.querySelector('#yearSelect');
        const slugInput = overlay.querySelector('#slugInput');

        // Génération de slug en temps réel unique par établissement cible
        const updateSlugField = () => {
            const classe = classInput.value.trim();
            const selectedOption = yearSelect.options[yearSelect.selectedIndex];
            const libelle = selectedOption ? selectedOption.getAttribute('data-libelle') || '' : '';

            // Récupérer le nom de l'école sélectionnée dans la page d'origine
            const schoolName = schoolSelect ? schoolSelect.options[schoolSelect.selectedIndex].text : '';

            if (classe && libelle && schoolName) {
                // Le slug combinera désormais : nom-ecole + classe + annee
                const rawSlug = (schoolName + '-' + classe + '-' + libelle);
                slugInput.value = rawSlug
                    .toLowerCase()
                    .normalize('NFD')
                    .replace(/[\u0300-\u036f]/g, '')
                    .replace(/[^\w\s-]/g, '')
                    .replace(/\s+/g, '-')
                    .replace(/-+/g, '-')
                    .trim('-');
            } else {
                slugInput.value = '';
            }
        };

        classInput.addEventListener('input', updateSlugField);
        yearSelect.addEventListener('change', updateSlugField);
        
        overlay.querySelector('#submitNewListBtn').addEventListener('click', () => saveNewList(schoolId));

    } catch (error) {
        alert('❌ Erreur: ' + error.message);
    }
}

async function saveNewList(schoolId) {
    const yearId = document.getElementById('yearSelect').value;
    const classe = document.getElementById('classInput').value.trim();
    const titre = document.getElementById('titleInput').value.trim();
    const slug = document.getElementById('slugInput').value.trim();

    if (!schoolId || !yearId || !classe || !slug) {
        alert('⚠️ Veuillez remplir tous les champs obligatoires');
        return;
    }

    try {
        const res = await fetch(`${CONFIG.API_BASE}/school-lists`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                school_id: parseInt(schoolId),
                year_id: parseInt(yearId),
                classe: classe,
                titre: titre || classe,
                slug: slug
            })
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Erreur lors de la création');
        }

        alert('✅ Liste créée !');
        document.querySelector('.modal-overlay').remove();
        loadSchoolsForLists();
    } catch (error) {
        alert('❌ Erreur: ' + error.message);
    }
}

async function openEditListModal(listId) {
    try {
        const res = await fetch(`${CONFIG.API_BASE}/school-lists/${listId}/details`);
        const list = await res.json();

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal">
                <div class="modal-header">
                    <h2>✏️ Modifier la Liste</h2>
                    <button class="close-modal">&times;</button>
                </div>
                <div class="modal-body">
                    <form id="editListForm" style="max-width: 600px;">
                        <div class="form-group">
                            <label>Classe:</label>
                            <input type="text" id="editClassInput" value="${list.classe}" required>
                        </div>
                        <div class="form-group">
                            <label>Titre:</label>
                            <input type="text" id="editTitleInput" value="${list.titre || ''}" required>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button class="close-modal btn btn-secondary">Annuler</button>
                    <button class="btn btn-primary" id="updateListBtn">💾 Enregistrer</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        overlay.querySelector('#updateListBtn').addEventListener('click', () => updateList(listId));
    } catch (error) {
        alert('❌ Erreur: ' + error.message);
    }
}

async function updateList(listId) {
    const classe = document.getElementById('editClassInput').value.trim();
    const titre = document.getElementById('editTitleInput').value.trim();

    if (!classe || !titre) {
        alert('⚠️ Veuillez remplir tous les champs');
        return;
    }

    try {
        const res = await fetch(`${CONFIG.API_BASE}/school-lists/${listId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ classe, titre })
        });

        if (!res.ok) throw new Error('Erreur de mise à jour');

        alert('✅ Liste mise à jour !');
        document.querySelector('.modal-overlay').remove();
        loadSchoolsForLists();
    } catch (error) {
        alert('❌ Erreur: ' + error.message);
    }
}

async function openListItemsModal(listId) {
    try {
        // 1. Charger les articles de la liste
        const itemsRes = await fetch(`${CONFIG.API_BASE}/school-list-items/${listId}`);
        const items = await itemsRes.json();

        // 2. Charger le catalogue général pour la recherche et l'association des informations
        const productsRes = await fetch(`${CONFIG.API_BASE}/products`);
        const productsData = await productsRes.json();
        const products = productsData.items || [];

        // 3. Charger les détails de l'école et de l'année scolaire de cette liste spécifique
        const listDetailsRes = await fetch(`${CONFIG.API_BASE}/school-lists/${listId}/details`);
        const listDetails = await listDetailsRes.json();

        // Récupérer le nom de l'école de façon sécurisée
        const schoolName = document.getElementById('schoolSelect') 
            ? document.getElementById('schoolSelect').options[document.getElementById('schoolSelect').selectedIndex].text 
            : "Maison de la Presse Gabon";

        let itemsHTML = '';
        let subtotal = 0;

        // Générer le tableau HTML dynamique en utilisant la maquette physique de l'impression
        items.forEach((item, idx) => {
            const product = products.find(p => p.id === item.product_id);
            const price = item.prix_force !== null && item.prix_force !== undefined ? item.prix_force : (product ? product.prix_vente : 0);
            const rowTotal = price * item.quantite;

            subtotal += rowTotal;

            itemsHTML += `
                <tr data-item-id="${item.id}" data-product-id="${item.product_id}">
                    <td class="center">
                        <div class="line-number">${idx + 1}</div>
                    </td>
                    <td class="center">
                        <img class="book-image" src="${product?.image_url || 'https://via.placeholder.com/90x120'}" onerror="this.src='https://via.placeholder.com/90x120'">
                    </td>
                    <td>
                        <strong style="color: #001a70; font-size: 15px;">${product ? product.titre : (item.designation_libre || 'N/A')}</strong>
                    </td>
                    <td class="center" style="font-family: monospace; font-size: 14px;">
                        ${product ? product.code : 'N/A'}
                    </td>
                    <td class="center">
                        <!-- Input interactif de quantité intégré dans la maquette -->
                        <input type="number" class="item-qty-input" value="${item.quantite}" min="1" style="width: 60px; padding: 6px; text-align: center; font-weight: bold; border: 1.5px solid #d8def0; border-radius: 6px;">
                    </td>
                    <td class="center price">
                        <!-- Input interactif de prix forcé intégré dans la maquette -->
                        <input type="number" class="item-price-input" value="${item.prix_force || ''}" placeholder="${product ? product.prix_vente : ''}" style="width: 100px; padding: 6px; text-align: center; font-weight: bold; border: 1.5px solid #d8def0; border-radius: 6px; color: #001a70; font-size: 15px;">
                        <span style="font-size: 10px; display: block; color: #666; margin-top: 2px;">FCFA (Unitaire)</span>
                        
                        <!-- Affichage dynamique du total de la ligne en fonction de la quantité -->
                        <div style="font-size: 13px; font-weight: bold; color: #001a70; margin-top: 5px; border-top: 1px dashed #cbd5e1; padding-top: 3px;">
                            Total: <span class="row-total-value">${rowTotal.toLocaleString('fr-FR')}</span> F
                        </div>
                    </td>
                    <td class="center">
                        <button class="btn btn-danger btn-sm btn-delete-item-row" data-item-id="${item.id}" style="padding: 6px 12px; font-size: 12px; border-radius: 6px;">🗑️ Retirer</button>
                    </td>
                </tr>
            `;
        });

        // Calculs basés sur la remise unique de STATE
        const discountValue = Math.round(subtotal * (STATE.globalDiscount / 100));
        const totalTtc = subtotal - discountValue;

        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay items-modal-overlay';
        
        // Structure de la modale intégrant la maquette valorisée physique complète
        overlay.innerHTML = `
            <div class="modal modal-fullscreen">
                <div class="modal-header">
                    <h2>📝 Gérer & Valoriser la Liste Scolaire</h2>
                    <button class="close-modal">&times;</button>
                </div>
                <div class="modal-body" style="background:#eef2fb; padding: 25px;">
                    
                    <!-- ================= CONTRÔLE D'AJOUT (ZONE ADMIN) ================= -->
                    <div style="margin-bottom: 30px; background: white; padding: 20px; border-radius: 14px; box-shadow: 0 4px 15px rgba(0,0,0,0.05); max-width: 1200px; margin-left: auto; margin-right: auto; border: 1px solid #d8def0;">
                        <label style="display: block; margin-bottom: 10px; font-weight: bold; color: #001a70; font-size: 15px;">🔍 Ajouter un produit à cette maquette :</label>
                        <div style="display: grid; grid-template-columns: 1fr 100px 140px 200px; gap: 12px;">
                            <div style="position: relative;">
                                <input type="text" id="productSearch" placeholder="Rechercher un produit par titre ou code-barres..." style="width: 100%; padding: 12px; border: 1.5px solid #d8def0; border-radius: 8px; font-size: 14px;">
                                <div id="productSearchResults" style="position: absolute; top: 100%; left: 0; right: 0; background: white; border: 1px solid #ddd; max-height: 250px; overflow-y: auto; display: none; z-index: 10; box-shadow: 0 10px 25px rgba(0,0,0,0.1); border-radius: 0 0 8px 8px;"></div>
                            </div>
                            <input type="number" id="productQty" value="1" min="1" style="padding: 12px; border: 1.5px solid #d8def0; border-radius: 8px; text-align: center; font-weight: bold; font-size: 14px;">
                            <button class="btn btn-primary" id="addAndRefreshBtn" style="padding: 12px 20px; width: 100%;">➕ Ajouter</button>
                            <button class="btn btn-info" id="importPlatformBtn" style="padding: 12px 20px; width: 100%;">🔄 Importer Plateforme</button>
                        </div>
                        
                        <!-- ✅ SECTION INTERACTIVE : Configuration directe de la remise globale de cette liste (0% par défaut) -->
                        <div style="margin-top: 15px; padding-top: 15px; border-top: 1.5px dashed #cbd5e1; display: flex; gap: 20px; align-items: center;">
                            <span style="font-weight: bold; color: #001a70; font-size: 14px;">⚙️ Configuration de la remise globale :</span>
                            <div style="display: flex; align-items: center; gap: 8px;">
                                <label style="font-size: 13px;">Taux de remise :</label>
                                <input type="number" id="listGlobalDiscount" value="${STATE.globalDiscount}" min="0" max="100" style="width: 80px; padding: 6px; border: 1.5px solid #d8def0; border-radius: 8px; text-align: center; font-weight: bold;">
                                <span style="font-weight: bold; color: #001a70;">%</span>
                            </div>
                        </div>

                        <div id="selectedProductInfo" style="margin-top: 12px; padding: 10px; background: #e8f4f8; border-radius: 6px; display: none; border-left: 4px solid #3b82f6;"></div>
                    </div>

                    <!-- ================= MAQUETTE PREVIEW PHYSIQUE ================= -->
                    <div class="page-list-details" style="width: 1200px; margin: auto; background: white; border-radius: 18px; overflow: hidden; box-shadow: 0 10px 40px rgba(0,0,0,0.10); color: #111;">
                        
                        <!-- HEADER -->
                        <div class="header" style="display: flex; justify-content: space-between; padding: 25px 35px; border-bottom: 6px solid #001a70; background: white;">
                            <div class="logo-zone" style="display: flex; gap: 25px; align-items: center;">
                                <div class="logo-text">
                                    <h1 style="font-size: 48px; line-height: 48px; color: #111; font-weight: 800; margin: 0;">Maison de<br>la Presse<br><span style="color: #f2b300;">Gabon</span></h1>
                                    <p style="margin-top: 8px; color: #001a70; font-style: italic; font-size: 20px;">Lire, apprendre, réussir !</p>
                                </div>
                            </div>
                            <div class="contact-zone" style="display: flex; gap: 40px; align-items: flex-start;">
                                <div class="contact-block" style="font-size: 14px; line-height: 1.8; color: #111;">
                                    📞 011 72 21 31<br>
                                    📞 011 77 26 95<br>
                                    🟢 WhatsApp : 066 956 027<br>
                                    ✉️ ipc369@yahoo.fr<br>
                                    🌐 www.maisondelapressegabon.com
                                </div>
                                <div class="shop-box" style="background: #001a70; color: white; padding: 15px 25px; border-radius: 12px; font-size: 16px; font-weight: bold; text-align: center;">
                                    2 MAGASINS<br><br>
                                    📍 GLASS<br>
                                    📍 OKALA
                                </div>
                            </div>
                        </div>

                        <!-- TOP BAR -->
                        <div class="top-bar" style="background: #001a70; color: white; display: flex; justify-content: space-around; padding: 15px 20px; font-size: 15px; font-weight: bold; border-radius: 0;">
                            <div>📋 LISTE VALORISÉE</div>
                            <div>🛡️ ENGAGEMENTS</div>
                            <div>🎁 COUVERTURE GRATUITE</div>
                        </div>

                        <!-- TITLE -->
                        <div class="title-section" style="display: flex; justify-content: space-between; align-items: center; padding: 30px 35px; background: white;">
                            <div class="title-left">
                                <div class="main-title" style="font-size: 48px; line-height: 1.1; font-weight: bold; color: #001a70;">
                                    LISTE SCOLAIRE<br>
                                    <span style="color: #f2b300;">VALORISÉE</span>
                                </div>
                            </div>
                            <div class="class-box" style="background: #001a70; color: white; padding: 18px 28px; border-radius: 12px; font-size: 18px; text-align: center; font-weight: bold; width: auto; min-width: 250px;">
                                ${listDetails.classe.toUpperCase()}<br>
                                <span style="font-size: 12px; font-weight: normal; color: #cbd5e1;">${schoolName.toUpperCase()}</span>
                            </div>
                        </div>

                        <!-- CLIENT INFO -->
                        <div class="client-box" style="margin: 0 35px 20px 35px; border: 2px solid #d8def0; border-radius: 14px; padding: 18px; background: #f8fafc;">
                            <div class="client-title" style="background: #001a70; color: white; display: inline-block; padding: 6px 14px; border-radius: 8px; font-size: 13px; margin-bottom: 12px; font-weight: bold;">
                                CLIENT
                            </div>
                            <div class="client-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; font-size: 13px; color: #333;">
                                <div>Nom & prénom : _______________________</div>
                                <div>Tél (WhatsApp) : _______________________</div>
                                <div>Classe : ${listDetails.classe}</div>
                                <div>Observations : _______________________</div>
                            </div>
                        </div>

                        <!-- TABLE DE PREVIEW INTERACTIVE -->
                        <div class="table-wrapper" style="padding: 0 35px; background: white;">
                            <table class="maquette-table" style="width: 100%; border-collapse: collapse;">
                                <thead style="background: #001a70; color: white;">
                                    <tr>
                                        <th style="padding: 12px 10px; font-size: 12px;">N°</th>
                                        <th style="padding: 12px 10px; font-size: 12px;">VISUEL</th>
                                        <th style="padding: 12px 10px; font-size: 12px; text-align: left;">DÉSIGNATION</th>
                                        <th style="padding: 12px 10px; font-size: 12px;">ISBN / EAN</th>
                                        <th style="padding: 12px 10px; font-size: 12px;">QTÉ</th>
                                        <th style="padding: 12px 10px; font-size: 12px;">PRIX DE VENTE</th>
                                        <th style="padding: 12px 10px; font-size: 12px;">ACTION</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${itemsHTML || '<tr><td colspan="7" style="text-align: center; padding: 30px; color: #94a3b8; font-style: italic;">Aucun article dans la liste. Recherchez un produit ci-dessus pour le rajouter.</td></tr>'}
                                </tbody>
                            </table>
                        </div>

                        <!-- OCCASION SECTION -->
                        <div class="occase-row" style="display: flex; gap: 15px; padding: 15px 35px; background: white;">
                            <div class="occase-box" style="flex: 1; border: 2px solid #d8def0; border-radius: 12px; padding: 12px 18px; display: flex; align-items: center; gap: 10px; font-size: 13px; font-weight: bold; color: #333;">
                                📚 LIVRES SCOLAIRES D'OCCASION
                            </div>
                            <div class="occase-box" style="flex: 1; border: 2px solid #d8def0; border-radius: 12px; padding: 12px 18px; display: flex; align-items: center; gap: 10px; font-size: 13px; font-weight: bold; color: #333;">
                                🌱 Donnez une seconde vie aux livres
                            </div>
                        </div>

                        <!-- TOTALS SECTION (LIVE PREVIEW COORDONNÉE) -->
                        <div class="total-wrapper" style="display: flex; justify-content: flex-end; padding: 20px 35px; background: white;">
                            <!-- Zone de calculs dynamique de la remise unique variable -->
                            <div class="total-box" id="interactiveTotalBox" style="width: 440px; border-radius: 12px; overflow: hidden; border: 2px solid #d8def0;">
                                <div class="total-line total-blue" style="display: flex; justify-content: space-between; padding: 12px 20px; font-size: 14px; font-weight: bold; background: #001a70; color: white;">
                                    <span>TOTAL AVANT REMISE</span>
                                    <span>${subtotal.toLocaleString('fr-FR')} FCFA</span>
                                </div>
                                <div class="total-line total-yellow" style="display: flex; justify-content: space-between; padding: 12px 20px; font-size: 14px; font-weight: bold; background: #fef08a; color: #854d0e;">
                                    <span>REMISE GLOBALE ${STATE.globalDiscount}%</span>
                                    <span>- ${discountValue.toLocaleString('fr-FR')} FCFA</span>
                                </div>
                                <div class="total-line total-blue" style="display: flex; justify-content: space-between; padding: 12px 20px; font-size: 15px; font-weight: bold; background: #f2b300; color: #111;">
                                    <span>TOTAL TTC FINAL</span>
                                    <span>${totalTtc.toLocaleString('fr-FR')} FCFA</span>
                                </div>
                            </div>
                        </div>

                        <!-- PAYMENT INFORMATION -->
                        <div class="payment-row" style="display: flex; justify-content: space-between; align-items: center; padding: 15px 35px; gap: 15px; background: white; border-top: 1.5px dashed #e2e8f0;">
                            <div class="payment-box" style="flex: 1; border: 2px solid #d8def0; border-radius: 12px; padding: 12px; font-size: 12px; text-align: center; color: #333;">
                                MOYENS DE PAIEMENT ACCEPTÉS<br><br>
                                <div class="airtel" style="color: red; font-size: 24px; font-weight: bold; margin-top: 5px;">M4010</div>
                            </div>
                            <div class="payment-box" style="height: 90px; display: flex; align-items: center; justify-content: center;">
                                PAIEMENT SÉCURISÉ<br>
                                www.maisondelapressegabonairtel.com
                            </div>
                            <div class="payment-box" style="height: 90px; display: flex; align-items: center; justify-content: center;">
                                Conditions générales de ventes disponibles en magasin
                            </div>
                        </div>

                        <!-- FOOTER -->
                        <div class="footer" style="background: #001a70; color: white; padding: 12px 35px; display: flex; justify-content: space-between; align-items: center; font-size: 11px;">
                            <div>La Maison de la Presse Gabon, partenaire privilégié de la réussite scolaire.</div>
                            <div>Ce document est une liste valorisée et non un devis.</div>
                        </div>

                    </div>
                </div>
                <div class="modal-footer">
                    <button class="close-modal btn btn-secondary">Fermer</button>
                    <button class="btn btn-primary" id="saveItemsListBtn">💾 Enregistrer la valorisation</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        // --- GESTION DE LA RECHERCHE ET DES LISTENERS DANS LA MODALE ---
        const searchInput = overlay.querySelector('#productSearch');
        const searchResults = overlay.querySelector('#productSearchResults');
        const selectedInfo = overlay.querySelector('#selectedProductInfo');

        searchInput.addEventListener('input', (e) => {
            const query = e.target.value.toLowerCase().trim();
            if (query.length < 1) {
                searchResults.style.display = 'none';
                selectedInfo.style.display = 'none';
                STATE.selectedProductIdFromSearch = null;
                return;
            }

            const filtered = products.filter(p => 
                (p.titre && p.titre.toLowerCase().includes(query)) || 
                (p.code && p.code.toLowerCase().includes(query))
            );

            if (filtered.length === 0) {
                searchResults.innerHTML = '<div style="padding: 12px; color: #94a3b8; text-align: center;">❌ Aucun produit trouvé</div>';
                searchResults.style.display = 'block';
                return;
            }

            searchResults.innerHTML = filtered.map(p => `
                <div class="search-result-item" data-id="${p.id}" data-titre="${p.titre}" data-code="${p.code}" data-price="${p.prix_vente}" style="padding: 10px; cursor: pointer; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <strong style="color: #001a70; font-size: 13px;">${p.titre}</strong><br>
                        <small style="color: #64748b;">Code: ${p.code}</small>
                    </div>
                    <div style="font-weight: bold; color: #22c55e;">${p.prix_vente.toLocaleString('fr-FR')} F</div>
                </div>
            `).join('');
            searchResults.style.display = 'block';

            // Sélectionner un produit
            searchResults.querySelectorAll('.search-result-item').forEach(item => {
                item.addEventListener('click', () => {
                    STATE.selectedProductIdFromSearch = item.dataset.id;
                    searchInput.value = item.dataset.titre;
                    searchResults.style.display = 'none';
                    selectedInfo.innerHTML = `Sélectionné : <strong>${item.dataset.titre}</strong> | Code : ${item.dataset.code} | Prix : ${parseFloat(item.dataset.price).toLocaleString('fr-FR')} FCFA`;
                    selectedInfo.style.display = 'block';
                });
            });
        });

        // Fermer les résultats si clic extérieur
        document.addEventListener('click', (e) => {
            if (!searchInput.contains(e.target) && !searchResults.contains(e.target)) {
                searchResults.style.display = 'none';
            }
        });

        // ✅ RECALCUL DYNAMIQUE ET SÉLECTIF EN TEMPS RÉEL (Modifiable par l'utilisateur)
        const recalculateTotals = () => {
            let newSubtotal = 0;
            const rows = overlay.querySelectorAll('tbody tr');
            
            // Récupération de la remise globale saisie à la volée
            const listGlobalDiscountInput = overlay.querySelector('#listGlobalDiscount');
            const currentGlobalDiscount = listGlobalDiscountInput ? (parseFloat(listGlobalDiscountInput.value) || 0) : STATE.globalDiscount;
            
            // Sauvegarde dans le STATE pour assurer la cohérence globale
            STATE.globalDiscount = currentGlobalDiscount;
            saveShoppingList(); // Persiste localement
            
            rows.forEach(row => {
                const qtyInput = row.querySelector('.item-qty-input');
                const priceInput = row.querySelector('.item-price-input');
                const rowTotalValue = row.querySelector('.row-total-value');
                if (!qtyInput || !priceInput) return;

                const qty = parseInt(qtyInput.value) || 1;
                const price = parseFloat(priceInput.value) || parseFloat(priceInput.placeholder) || 0;
                const rowTotal = price * qty;

                newSubtotal += rowTotal;

                // Mettre à jour l'affichage du total de la ligne
                if (rowTotalValue) {
                    rowTotalValue.textContent = rowTotal.toLocaleString('fr-FR');
                }
            });

            const newDiscountValue = Math.round(newSubtotal * (currentGlobalDiscount / 100));
            const newTotalTtc = newSubtotal - newDiscountValue;

            // Remplacer dynamiquement le contenu du panneau des totaux à l'écran
            const totalBox = overlay.querySelector('#interactiveTotalBox');
            if (totalBox) {
                totalBox.innerHTML = `
                    <div class="total-line total-blue" style="display: flex; justify-content: space-between; padding: 12px 20px; font-size: 14px; font-weight: bold; background: #001a70; color: white;">
                        <span>TOTAL AVANT REMISE</span>
                        <span>${newSubtotal.toLocaleString('fr-FR')} FCFA</span>
                    </div>
                    <div class="total-line total-yellow" style="display: flex; justify-content: space-between; padding: 12px 20px; font-size: 14px; font-weight: bold; background: #fef08a; color: #854d0e;">
                        <span>REMISE SÉLECTIVE ${currentGlobalDiscount}%</span>
                        <span>- ${newDiscountValue.toLocaleString('fr-FR')} FCFA</span>
                    </div>
                    <div class="total-line total-blue" style="display: flex; justify-content: space-between; padding: 12px 20px; font-size: 15px; font-weight: bold; background: #f2b300; color: #111;">
                        <span>TOTAL TTC FINAL</span>
                        <span>${newTotalTtc.toLocaleString('fr-FR')} FCFA</span>
                    </div>
                `;
            }
        };

        // Écouter en temps réel les changements sur les quantités, prix et sur le taux de remise globale
        overlay.querySelectorAll('.item-qty-input, .item-price-input, #listGlobalDiscount').forEach(input => {
            input.addEventListener('input', recalculateTotals);
        });

        // Événement d'ajout d'un produit
        overlay.querySelector('#addAndRefreshBtn').addEventListener('click', () => addProductToList(listId));

        // Liaison avec le bouton d'importation depuis la plateforme
        overlay.querySelector('#importPlatformBtn').addEventListener('click', async () => {
            if (confirm("Voulez-vous extraire et injecter automatiquement les articles de cette classe depuis pages_libres.php ?")) {
                try {
                    const importBtn = overlay.querySelector('#importPlatformBtn');
                    importBtn.disabled = true;
                    importBtn.textContent = "⏳ Importation...";
                    
                    const res = await fetch(`${CONFIG.API_BASE}/school-lists/${listId}/import-from-platform`, { method: 'POST' });
                    if (!res.ok) throw new Error('Erreur réseau');
                    
                    alert("✅ Importation, appariement et valorisation réussis !");
                    overlay.remove();
                    openListItemsModal(listId); // Rafraîchit l'affichage maquette
                } catch (e) {
                    alert("❌ Erreur : " + e.message);
                    const importBtn = overlay.querySelector('#importPlatformBtn');
                    importBtn.disabled = false;
                    importBtn.textContent = "🔄 Importer Plateforme";
                }
            }
        });

        // Événement d'enregistrement des modifications de quantité ou de prix
        overlay.querySelector('#saveItemsListBtn').addEventListener('click', () => saveListItems(listId));

        // Événement de suppression dynamique sur chaque ligne
        overlay.querySelectorAll('.btn-delete-item-row').forEach(btn => {
            btn.addEventListener('click', () => deleteListItem(btn.dataset.itemId, listId));
        });

    } catch (error) {
        alert('❌ Erreur de chargement de la maquette d\'articles : ' + error.message);
    }
}

async function addProductToList(listId) {
    const productId = STATE.selectedProductIdFromSearch;
    const qty = parseInt(document.getElementById('productQty').value) || 1;

    if (!productId) {
        alert('⚠️ Veuillez sélectionner un produit dans la liste déroulante.');
        return;
    }

    try {
        const res = await fetch(`${CONFIG.API_BASE}/school-list-items`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                list_id: parseInt(listId),
                product_id: parseInt(productId),
                quantite: qty
            })
        });

        if (!res.ok) throw new Error('Erreur de serveur');

        alert('✅ Produit ajouté !');
        STATE.selectedProductIdFromSearch = null;
        
        // Rafraîchir l'affichage de la modale directement (sans reload de page)
        const modal = document.querySelector('.items-modal-overlay');
        if (modal) modal.remove();
        openListItemsModal(listId);
    } catch (error) {
        alert('❌ Erreur lors de l\'ajout : ' + error.message);
    }
}

async function saveListItems(listId) {
    const modal = document.querySelector('.items-modal-overlay');
    if (!modal) return;

    const rows = modal.querySelectorAll('tbody tr');
    const updatePromises = [];

    for (const row of rows) {
        const itemId = row.dataset.itemId;
        if (!itemId) continue;

        const quantite = parseInt(row.querySelector('.item-qty-input').value) || 1;
        const priceVal = row.querySelector('.item-price-input').value;
        const prix_force = priceVal ? parseFloat(priceVal) : null;

        updatePromises.push(
            fetch(`${CONFIG.API_BASE}/school-list-items/${itemId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ quantite: quantite, prix_force: prix_force })
            })
        );
    }

    try {
        await Promise.all(updatePromises);
        alert('✅ Modifications enregistrées avec succès !');
        modal.remove();
        loadSchoolsForLists(); // Recharge la liste principale en arrière-plan
    } catch (error) {
        alert('❌ Erreur lors de la sauvegarde : ' + error.message);
    }
}

async function deleteListItem(itemId, listId) {
    if (confirm('Êtes-vous sûr de vouloir retirer ce produit de la liste ?')) {
        try {
            const res = await fetch(`${CONFIG.API_BASE}/school-list-items/${itemId}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Erreur serveur');
            alert('✅ Article retiré de la liste !');
            
            // Rafraîchit dynamiquement la vue des articles sans recharger toute la page
            const modal = document.querySelector('.items-modal-overlay');
            if (modal) modal.remove();
            openListItemsModal(listId);
        } catch (error) {
            alert('❌ Erreur lors de la suppression : ' + error.message);
        }
    }
}

async function generateListPDF(id) {
    try {
        // Envoi de la remise globale en paramètre d'URL au serveur pour aligner le PDF généré
        const response = await fetch(`${CONFIG.API_BASE}/school-lists-pdf/${id}/pdf?discount_percent=${STATE.globalDiscount}`);
        if (!response.ok) throw new Error('Erreur de génération');

        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `liste_${id}.pdf`;
        a.click();
        window.URL.revokeObjectURL(url);
    } catch (error) {
        alert('❌ Erreur de génération du PDF: ' + error.message);
    }
}

async function deleteList(id, schoolId, yearId) {
    if (confirm('Êtes-vous sûr de vouloir supprimer définitivement cette liste ?')) {
        try {
            const res = await fetch(`${CONFIG.API_BASE}/school-lists/${id}`, { method: 'DELETE' });
            if (!res.ok) throw new Error('Erreur serveur');
            alert('✅ Liste supprimée !');
            loadClassesForLists(schoolId, yearId); // Recharge les listes de la classe sélectionnée
        } catch (error) {
            alert('❌ Erreur: ' + error.message);
        }
    }
}


async function openDuplicateListModal(listId, currentSchoolId, yearId) {
    try {
        // 1. Récupérer tous les établissements pour le sélecteur
        const res = await fetch(`${CONFIG.API_BASE}/schools`);
        const schools = await res.json();

        // 2. Récupérer le libellé de l'année active depuis le select principal
        const yearSelect = document.getElementById('yearSelectLists');
        const yearLabel = yearSelect ? yearSelect.options[yearSelect.selectedIndex].text : '';

        // 3. Créer la fenêtre modale interactive
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal" style="max-width: 500px;">
                <div class="modal-header">
                    <h2>📋 Dupliquer la liste scolaire</h2>
                    <button class="close-modal">&times;</button>
                </div>
                <div class="modal-body">
                    <form id="duplicateForm">
                        <div class="form-group" style="margin-bottom: 15px;">
                            <label style="display: block; font-weight: bold; margin-bottom: 5px;">Établissement cible :</label>
                            <select id="dupSchoolId" style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid #ccc;">
                                ${schools.map(s => `
                                    <option value="${s.id}" ${parseInt(s.id) === parseInt(currentSchoolId) ? 'selected' : ''}>
                                        ${s.nom}
                                    </option>
                                `).join('')}
                            </select>
                        </div>
                        <div class="form-group" style="margin-bottom: 15px;">
                            <label style="display: block; font-weight: bold; margin-bottom: 5px;">Nom de la nouvelle classe :</label>
                            <input type="text" id="dupClasse" placeholder="Ex: 6ème B" required style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid #ccc;">
                        </div>
                        <div class="form-group" style="margin-bottom: 15px;">
                            <label style="display: block; font-weight: bold; margin-bottom: 5px;">Slug (Généré) :</label>
                            <input type="text" id="dupSlug" readonly style="width: 100%; padding: 8px; border-radius: 4px; border: 1px solid #ccc; background: #eef2f6;">
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button class="close-modal btn btn-secondary">Annuler</button>
                    <button class="btn btn-primary" id="confirmDuplicateBtn">💾 Lancer la copie</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);

        const classInput = overlay.querySelector('#dupClasse');
        const slugInput = overlay.querySelector('#dupSlug');

        // Génération de slug en temps réel semblable au système existant
        const updateSlugField = () => {
            const classe = classInput.value.trim();
            const selectedOption = yearSelect.options[yearSelect.selectedIndex];
            const libelle = selectedOption ? selectedOption.getAttribute('data-libelle') || '' : '';

            // NOUVEAU : Récupérer le nom de l'école active pour rendre le slug unique par établissement
            const schoolSelect = document.getElementById('schoolSelect');
            const schoolName = schoolSelect ? schoolSelect.options[schoolSelect.selectedIndex].text : '';

            if (classe && libelle && schoolName) {
                // Le slug combinera désormais : nom-ecole + classe + annee
                const rawSlug = (schoolName + '-' + classe + '-' + libelle);
                slugInput.value = rawSlug
                    .toLowerCase()
                    .normalize('NFD')
                    .replace(/[\u0300-\u036f]/g, '')
                    .replace(/[^\w\s-]/g, '')
                    .replace(/\s+/g, '-')
                    .replace(/-+/g, '-')
                    .trim('-');
            } else {
                slugInput.value = '';
            }
        };

        classInput.addEventListener('input', updateSlugField);

        // Confirmation de l'action
        overlay.querySelector('#confirmDuplicateBtn').addEventListener('click', () => {
            const targetSchoolId = overlay.querySelector('#dupSchoolId').value;
            const newClassName = classInput.value.trim();
            const finalSlug = slugInput.value.trim();

            if (!targetSchoolId || !newClassName || !finalSlug) {
                alert('⚠️ Veuillez remplir tous les champs obligatoires.');
                return;
            }

            submitDuplication(listId, targetSchoolId, newClassName, finalSlug, currentSchoolId, yearId);
        });

    } catch (error) {
        alert('❌ Erreur lors de l\'initialisation : ' + error.message);
    }
}

async function submitDuplication(listId, targetSchoolId, newClassName, slug, currentSchoolId, yearId) {
    try {
        const res = await fetch(`${CONFIG.API_BASE}/school-lists/${listId}/duplicate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                school_id: parseInt(targetSchoolId),
                classe: newClassName,
                slug: slug
            })
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || 'Une erreur est survenue lors du traitement.');
        }

        alert('✅ Liste scolaire dupliquée avec succès !');

        // Suppression de la modale d'affichage
        const overlay = document.querySelector('.modal-overlay');
        if (overlay) overlay.remove();

        // Rechargement des listes de la vue en cours (école d'origine)
        loadClassesForLists(currentSchoolId, yearId);

    } catch (error) {
        alert('❌ Échec de la copie : ' + error.message);
    }
}