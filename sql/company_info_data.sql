--
-- PostgreSQL database dump
--


-- Dumped from database version 16.13 (Debian 16.13-1.pgdg13+1)
-- Dumped by pg_dump version 16.13 (Debian 16.13-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: company_info; Type: TABLE DATA; Schema: public; Owner: walton
--

COPY public.company_info (id, key, value) FROM stdin;
1	company_name	WaltonMarket
2	tagline	Smart Home Automation Products
3	location	Al Husain Plaza, M.A Jinnah Road, Okara, Punjab, Pakistan
4	cities_served	Lahore, Islamabad, Multan, Faisalabad, Okara, Sahiwal
5	online_consultation	Yes — we also provide online consultation for cities not listed
6	whatsapp	+923010756404
7	email	thewaltonmarket@gmail.com
8	website	waltonmarket.com
9	working_hours	Mon-Sat, 9am-6pm PKT
10	about	WaltonMarket specializes in smart home automation products that make your life easier. We offer WiFi smart switches, bulbs, sensors, Google Home devices, and complete home automation solutions.
11	delivery_time	We deliver within 2-5 business days across Pakistan. Shipping is handled by PostEx courier service.
12	payment_methods	Cash on Delivery (COD) and Online Payment (Bank Transfer, Easypaisa, JazzCash)
13	return_policy	We offer a 7-day return policy. Returns accepted for: wrong item, damaged/defective on arrival, not functioning as advertised. Product must be unused, in original condition with all accessories/packaging intact. Return request must be initiated within 7 days of delivery. Non-returnable: products damaged by misuse/drops/power issues, items installed by non-professionals, custom orders or clearance items. Items not liked by customer can only be exchanged once (shipping cost may apply). Contact support within 3 days with order number, 3+ product photos, and issue details. Refunds processed within 3-5 working days via bank transfer, Easypaisa, or JazzCash. COD customers must provide bank/wallet details. Exchange available subject to stock. Return shipping covered by us for damaged/wrong/defective items, otherwise borne by customer.
15	bank_name	MCB Limited
16	bank_account	YOUR_BANK_ACCOUNT
17	bank_iban	YOUR_BANK_IBAN
18	bank_title	YOUR_BANK_ACCOUNT_TITLE
19	service_areas	We provide smart home installation services in all major cities of Punjab including Lahore, Faisalabad, Multan, Islamabad, Sahiwal, Okara, and all other cities of Punjab. We also deliver products nationwide across Pakistan.
14	warranty	All Walton Market products come with a 1-Year Limited Warranty from the date of delivery. Coverage includes manufacturing defects, software/connectivity issues, and product malfunctions under normal usage. NOT covered: physical damage, burnt due to voltage fluctuation, tampered/repaired by unauthorized personnel, used without proper electrical protection. To claim: provide original physical receipt, complete product packaging with box, user manual, and all accessories. Contact via WhatsApp or call with order number, issue description, and at least 3 photos/video. Replacement or repair processed within 7-10 working days. Warranty is non-transferable and valid only for original buyer from date of delivery.
\.


--
-- Name: company_info_id_seq; Type: SEQUENCE SET; Schema: public; Owner: walton
--

SELECT pg_catalog.setval('public.company_info_id_seq', 20, true);


--
-- PostgreSQL database dump complete
--
