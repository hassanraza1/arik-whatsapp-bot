// Executes structured router items only. cartOp set replaces quantity. cartOp remove subtracts.
const products = Array.isArray($json.products) ? $json.products : [];
let cart = Array.isArray($json.cart) ? $json.cart.map(c => ({ ...c })) : [];
let lastProduct = $json.lastProduct || null;
let cartOp = String($json.cartOp || 'add').toLowerCase();
if (cartOp !== 'set' && cartOp !== 'remove') cartOp = 'add';

function cleanItems(raw) {
  const out = [];
  if (!Array.isArray(raw)) return out;
  for (const it of raw) {
    if (!it) continue;
    const id = Number(it.productId);
    const qty = Number(it.qty);
    const p = products.find(x => Number(x.id) === id);
    if (!p || !p.product_name) continue;
    if (!Number.isFinite(qty) || qty < 1 || qty > 999) continue;
    out.push({ product: p, qty: Math.round(qty) });
  }
  return out;
}

let parsed = cleanItems($json.items);
if (!parsed.length && $json.useLastProduct && lastProduct && lastProduct.id) {
  const qty = Number($json.qty);
  const p = products.find(x => Number(x.id) === Number(lastProduct.id));
  if (p && Number.isFinite(qty) && qty >= 1 && qty <= 999) {
    parsed = [{ product: p, qty: Math.round(qty) }];
  }
}
if (!parsed.length && (cartOp === 'set' || cartOp === 'remove') && cart.length === 1) {
  const qty = Number($json.qty);
  const p = products.find(x => x.product_name === cart[0].name);
  if (p && Number.isFinite(qty) && qty >= 1 && qty <= 999) {
    parsed = [{ product: p, qty: Math.round(qty) }];
  }
}

if (!parsed.length) {
  const reply = 'Please tell me which product you want!\n\nType *catalogue* to keep browsing.\nType *menu* to return to main menu.';
  return [{ json: { ...$json, reply, cart, items: [], cartOp } }];
}

const added = [];
const skipped = [];
const missing = [];
for (const it of parsed) {
  const stock = String(it.product.stock || '').toLowerCase();
  const inStock = !stock || stock.includes('in stock') || stock.includes('available') || stock.includes('yes');
  if (!inStock && cartOp !== 'remove') {
    skipped.push(it.product.product_name);
    continue;
  }
  const existing = cart.find(c => c.name === it.product.product_name);
  if (cartOp === 'remove') {
    if (!existing) {
      missing.push(it.product.product_name);
      continue;
    }
    existing.qty = Number(existing.qty || 0) - it.qty;
  } else if (cartOp === 'set') {
    if (existing) existing.qty = it.qty;
    else cart.push({ name: it.product.product_name, price: it.product.price, qty: it.qty });
  } else if (existing) {
    existing.qty = Number(existing.qty || 0) + it.qty;
  } else {
    cart.push({ name: it.product.product_name, price: it.product.price, qty: it.qty });
  }
  added.push(it);
  lastProduct = it.product;
}
cart = cart.filter(c => Number(c.qty) > 0);

let reply = '';
if (!added.length) {
  if (missing.length) {
    reply = 'I could not match that to a line already in your cart.\n\nType *cart* to see the exact lines.\nType *menu* to return to main menu.';
  } else {
    reply = 'Sorry, ' + skipped.join(', ') + ' is currently out of stock.\n\nType *catalogue* to browse available products.\nType *menu* to return to main menu.';
  }
  return [{ json: { ...$json, reply, cart, cartOp } }];
}

const total = cart.reduce((s, c) => s + Number(c.price) * Number(c.qty), 0);
const cartLines = cart.length
  ? cart.map((c, i) => (i + 1) + '. *' + c.name + '* x' + c.qty + ' — PKR ' + (Number(c.price) * Number(c.qty))).join('\n')
  : 'Your cart is empty.';
const changedLines = added.map(it => it.qty + ' x ' + it.product.product_name).join('\n');
const verb = cartOp === 'set' ? 'Updated quantity' : (cartOp === 'remove' ? 'Removed from cart' : 'Added to cart');
reply = verb + ':\n' + changedLines + '\n\nYour Cart (' + cart.length + ' items):\n\n' + cartLines + '\n\nTotal: PKR ' + total + '\n\nType *catalogue* to keep browsing.\nType *checkout* when you are ready.\nType *menu* to return to main menu.';
return [{ json: { ...$json, reply, cart, lastProduct, cartOp, items: added.map(it => ({ productId: it.product.id, qty: it.qty })) } }];
