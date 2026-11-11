/* index.html: inline hodisa handlerlari (onclick="..." o'rniga). Avtomatik yaratilgan: CSP uchun. */
(function () {
  var R = window.SG_H = window.SG_H || {};
  R["h1"] = function (event) { openBizPage()
  };
  R["h2"] = function (event) { kirishOch()
  };
  R["h3"] = function (event) { toggleNav()
  };
  R["h4"] = function (event) { toggleNav();openBizPage()
  };
  R["h5"] = function (event) { toggleNav();kirishOch()
  };
  R["h6"] = function (event) { event.preventDefault();openHisobPage('narx')
  };
  R["h7"] = function (event) { showModal('loyiha')
  };
  R["h8"] = function (event) { showModal('montaj')
  };
  R["h9"] = function (event) { showModal('servis')
  };
  R["h10"] = function (event) { openMetroPage()
  };
  R["h11"] = function (event) { openXaridBolim()
  };
  R["h12"] = function (event) { openNegaPage()
  };
  R["h13"] = function (event) { openTolovPage()
  };
  R["h14"] = function (event) { openFaqPage()
  };
  R["h15"] = function (event) { submitForm(event,'contact')
  };
  R["h16"] = function (event) { closeXaridBolim()
  };
  R["h17"] = function (event) { openXaridKuzat()
  };
  R["h18"] = function (event) { this.style.color='#ff8a00';this.style.borderColor='rgba(120,170,235,0.55)'
  };
  R["h19"] = function (event) { this.style.color='#c8a830';this.style.borderColor='rgba(120,170,235,0.28)'
  };
  R["h20"] = function (event) { openKatPage('gorelka')
  };
  R["h21"] = function (event) { this.style.borderColor='rgba(60,140,225,0.65)';this.style.boxShadow='0 8px 32px rgba(60,140,225,0.12)'
  };
  R["h22"] = function (event) { this.style.borderColor='rgba(60,140,225,0.3)';this.style.boxShadow='none'
  };
  R["h23"] = function (event) { openKatPage('hisob')
  };
  R["h24"] = function (event) { this.style.borderColor='rgba(90,150,235,0.65)';this.style.boxShadow='0 8px 32px rgba(90,150,235,0.12)'
  };
  R["h25"] = function (event) { this.style.borderColor='rgba(90,150,235,0.3)';this.style.boxShadow='none'
  };
  R["h26"] = function (event) { openKatPage('ventil')
  };
  R["h27"] = function (event) { this.style.borderColor='rgba(70,160,230,0.65)';this.style.boxShadow='0 8px 32px rgba(70,160,230,0.12)'
  };
  R["h28"] = function (event) { this.style.borderColor='rgba(70,160,230,0.3)';this.style.boxShadow='none'
  };
  R["h29"] = function (event) { openCartPage()
  };
  R["h30"] = function (event) { clearCart()
  };
  R["h31"] = function (event) { closeNegaPage()
  };
  R["h32"] = function (event) { negaBolimga('nega-afzallik')
  };
  R["h33"] = function (event) { negaBolimga('nega-jarayon')
  };
  R["h34"] = function (event) { closeTolovPage()
  };
  R["h35"] = function (event) { selectPayment(this,'bank')
  };
  R["h36"] = function (event) { selectPayment(this,'online')
  };
  R["h37"] = function (event) { selectPayment(this,'shartnoma')
  };
  R["h38"] = function (event) { openInvoice()
  };
  R["h39"] = function (event) { closeBankPage()
  };
  R["h40"] = function (event) { copyBankCard()
  };
  R["h41"] = function (event) { closeBankPage();openInvoice('Bank o\'tkazmasi')
  };
  R["h42"] = function (event) { closeOnlinePage()
  };
  R["h43"] = function (event) { onlinePay('click')
  };
  R["h44"] = function (event) { onlinePay('payme')
  };
  R["h45"] = function (event) { onlinePay('apelsin')
  };
  R["h46"] = function (event) { closeShartnomaPage()
  };
  R["h47"] = function (event) { submitShartnoma()
  };
  R["h48"] = function (event) { if(event.target===this)closeInvoice()
  };
  R["h49"] = function (event) { closeInvoice()
  };
  R["h50"] = function (event) { submitForm(event,'invoice')
  };
  R["h51"] = function (event) { closeFaqPage()
  };
  R["h52"] = function (event) { closeGarelkaPage()
  };
  R["h53"] = function (event) { this.style.background='rgba(120,170,235,0.18)';this.style.color='#ff8a00';this.style.borderColor='rgba(120,170,235,0.55)'
  };
  R["h54"] = function (event) { this.style.background='rgba(120,170,235,0.08)';this.style.color='#c8a830';this.style.borderColor='rgba(120,170,235,0.28)'
  };
  R["h55"] = function (event) { grlRender()
  };
  R["h56"] = function (event) { this.style.background='rgba(120,170,235,0.22)'
  };
  R["h57"] = function (event) { this.style.background='rgba(120,170,235,0.12)'
  };
  R["h58"] = function (event) { if(event.target===this)grlInfoClose()
  };
  R["h59"] = function (event) { grlInfoClose()
  };
  R["h60"] = function (event) { this.style.background='rgba(120,170,235,0.15)';this.style.color='#ff8a00'
  };
  R["h61"] = function (event) { this.style.background='rgba(31,72,135,0.05)';this.style.color='#6a5820'
  };
  R["h62"] = function (event) { closeCartPage()
  };
  R["h63"] = function (event) { this.style.background='rgba(220,50,50,0.12)';this.style.color='#ff6b6b';this.style.borderColor='rgba(220,50,50,0.35)'
  };
  R["h64"] = function (event) { this.style.background='rgba(31,72,135,0.04)';this.style.color='#8b7820';this.style.borderColor='rgba(120,170,235,0.25)'
  };
  R["h65"] = function (event) { this.style.color='#8b7820';this.style.borderColor='rgba(120,170,235,0.25)'
  };
  R["h66"] = function (event) { cartCheckout()
  };
  R["h67"] = function (event) { this.style.boxShadow='0 4px 24px rgba(110,165,230,0.5),inset 0 1px 0 rgba(255,255,255,0.2)'
  };
  R["h68"] = function (event) { this.style.boxShadow='0 2px 16px rgba(120,170,235,0.35),inset 0 1px 0 rgba(255,255,255,0.15)'
  };
  R["h69"] = function (event) { closeXaridPage()
  };
  R["h70"] = function (event) { xaridBosqich(1)
  };
  R["h71"] = function (event) { xaridBosqich(2)
  };
  R["h72"] = function (event) { xaridBosqich(3)
  };
  R["h73"] = function (event) { xaridBosqich(4)
  };
  R["h74"] = function (event) { tumanTanlandi()
  };
  R["h75"] = function (event) { xaridYetkazish('kuryer')
  };
  R["h76"] = function (event) { xaridYetkazish('filialdan')
  };
  R["h77"] = function (event) { xaridKun('bugun')
  };
  R["h78"] = function (event) { xaridKun('ertaga')
  };
  R["h79"] = function (event) { xaridKun('sana')
  };
  R["h80"] = function (event) { xaridVaqtYangila()
  };
  R["h81"] = function (event) { xaridOraliq('09:00–12:00')
  };
  R["h82"] = function (event) { xaridOraliq('12:00–15:00')
  };
  R["h83"] = function (event) { xaridOraliq('15:00–18:00')
  };
  R["h84"] = function (event) { xaridOraliq('18:00–21:00')
  };
  R["h85"] = function (event) { izohQosh('Domofon kodi: ')
  };
  R["h86"] = function (event) { izohQosh('Eshikni taqillatmang')
  };
  R["h87"] = function (event) { izohQosh('Oldindan qo\'ng\'iroq qiling')
  };
  R["h88"] = function (event) { izohQosh('Qoldiring, o\'zim olaman')
  };
  R["h89"] = function (event) { xaridTolov('naqd')
  };
  R["h90"] = function (event) { xaridTolov('click')
  };
  R["h91"] = function (event) { xaridTolov('payme')
  };
  R["h92"] = function (event) { xaridTolov('karta')
  };
  R["h93"] = function (event) { xaridTolov('bolib')
  };
  R["h94"] = function (event) { setTimeout(xaridXulosa,0)
  };
  R["h95"] = function (event) { if(event.key==='Enter'){event.preventDefault();promoQollash();}
  };
  R["h96"] = function (event) { promoQollash()
  };
  R["h97"] = function (event) { xaridOrqaga()
  };
  R["h98"] = function (event) { xaridOldinga()
  };
  R["h99"] = function (event) { xulosaOch()
  };
  R["h100"] = function (event) { if(event.key==='Enter')xaridQidir()
  };
  R["h101"] = function (event) { xaridQidir()
  };
  R["h102"] = function (event) { closeKatPage()
  };
  R["h103"] = function (event) { katRender()
  };
  R["h104"] = function (event) { if(event.target===this)katInfoClose()
  };
  R["h105"] = function (event) { katInfoClose()
  };
  R["h106"] = function (event) { if(event.target===this)katHujjatYop()
  };
  R["h107"] = function (event) { katHujjatYop()
  };
  R["h108"] = function (event) { if(event.target===this)katResultClose()
  };
  R["h109"] = function (event) { closeHisobPage()
  };
  R["h110"] = function (event) { this.style.background='rgba(120,170,235,0.18)';this.style.borderColor='rgba(120,170,235,0.55)'
  };
  R["h111"] = function (event) { this.style.background='rgba(120,170,235,0.08)';this.style.borderColor='rgba(120,170,235,0.28)'
  };
  R["h112"] = function (event) { closeHisobPage();showModal('buyurtma')
  };
  R["h113"] = function (event) { closeBizPage()
  };
  R["h114"] = function (event) { qadriyatOch('jarayon')
  };
  R["h115"] = function (event) { qadriyatOch('jamoa')
  };
  R["h116"] = function (event) { qadriyatOch('kafolat')
  };
  R["h117"] = function (event) { closeBizPage();setTimeout(function(){document.getElementById('aloqa').scrollIntoView({behavior:'smooth'})},150)
  };
  R["h118"] = function (event) { qadriyatYop()
  };
  R["h119"] = function (event) { closeMetroPage()
  };
  R["h120"] = function (event) { metroTabKlavisha(event)
  };
  R["h121"] = function (event) { metroXizmatOch('kalibrovka', this)
  };
  R["h122"] = function (event) { metroXizmatOch('almashtirish', this)
  };
  R["h123"] = function (event) { metroXizmatOch('qiyoslov', this)
  };
  R["h124"] = function (event) { submitMetro(event)
  };
  R["h125"] = function (event) { this.style.borderColor='rgba(120,170,235,0.6)'
  };
  R["h126"] = function (event) { this.style.borderColor='rgba(120,170,235,0.2)'
  };
  R["h127"] = function (event) { if (event.target === this) metroOynaYop()
  };
  R["h128"] = function (event) { metroOynaYop()
  };
  R["h129"] = function (event) { if (event.target === this) metroBolimYop()
  };
  R["h130"] = function (event) { metroBolimYop()
  };
  R["h131"] = function (event) { closeLpgPage()
  };
  R["h132"] = function (event) { this.style.background='rgba(20,184,166,0.18)';this.style.borderColor='rgba(20,184,166,0.55)'
  };
  R["h133"] = function (event) { this.style.background='rgba(20,184,166,0.08)';this.style.borderColor='rgba(20,184,166,0.28)'
  };
  R["h134"] = function (event) { openBalonPage()
  };
  R["h135"] = function (event) { openRezervuarPage()
  };
  R["h136"] = function (event) { openBuyurtmaOyna()
  };
  R["h137"] = function (event) { closeRezervuarPage()
  };
  R["h138"] = function (event) { openBuyurtmaOyna(false,'rezervuar')
  };
  R["h139"] = function (event) { closeBalonPage()
  };
  R["h140"] = function (event) { if(event.target===this)closeBuyurtmaOyna()
  };
  R["h141"] = function (event) { closeBuyurtmaOyna()
  };
  R["h142"] = function (event) { submitLpg(event)
  };
  R["h143"] = function (event) { this.style.borderColor='rgba(20,184,166,0.6)'
  };
  R["h144"] = function (event) { this.style.borderColor='rgba(20,184,166,0.2)'
  };
  R["h145"] = function (event) { closeModalOutside(event)
  };
  R["h146"] = function (event) { closeModal()
  };
  R["h147"] = function (event) { kirishFonBosildi(event)
  };
  R["h148"] = function (event) { event.stopPropagation()
  };
  R["h149"] = function (event) { kirishYop()
  };
  R["h150"] = function (event) { kirishRolTanla('mijoz')
  };
  R["h151"] = function (event) { kirishDavomEt(event)
  };
  R["h152"] = function (event) { kirishTelefonTozala(this)
  };
  R["h153"] = function (event) { kirishRoyxatOch()
  };
  R["h154"] = function (event) { kirishRolgaQayt()
  };
  R["h155"] = function (event) { closeMijozPage()
  };
  R["h156"] = function (event) { mijozSendOtp(event)
  };
  R["h157"] = function (event) { mijozOtpBack()
  };
  R["h158"] = function (event) { mijozVerifyOtp(event)
  };
  R["h159"] = function (event) { this.value=this.value.replace(/\D/g,'')
  };
  R["h160"] = function (event) { mijozResendOtp()
  };
  R["h161"] = function (event) { mijozCompleteProfile(event)
  };
  R["h162"] = function (event) { mijozProfilTahrirla()
  };
  R["h163"] = function (event) { mijozLogout()
  };
  R["h164"] = function (event) { mijozTab('buyurtma')
  };
  R["h165"] = function (event) { mijozTab('tolov')
  };
  R["h166"] = function (event) { mijozTab('tarix')
  };
  R["h167"] = function (event) { mijozTab('sms')
  };
  R["h168"] = function (event) { mijozTab('monitoring')
  };
  R["h169"] = function (event) { mijozSubmitBuyurtma(event)
  };
  R["h170"] = function (event) { mijozSelectPayMethod(this,'click')
  };
  R["h171"] = function (event) { mijozSelectPayMethod(this,'payme')
  };
  R["h172"] = function (event) { mijozSelectPayMethod(this,'bank')
  };
  R["h173"] = function (event) { mijozConfirmPayment()
  };
  R["h174"] = function (event) { closeXodimPage()
  };
  R["h175"] = function (event) { xodimSendOtp(event)
  };
  R["h176"] = function (event) { xodimOtpBack()
  };
  R["h177"] = function (event) { xodimVerifyOtp(event)
  };
  R["h178"] = function (event) { xodimResendOtp()
  };
  R["h179"] = function (event) { xodimOtpReset()
  };
  R["h180"] = function (event) { xodimLogout()
  };
  R["h181"] = function (event) { xodimTab('buyurtmalar')
  };
  R["h182"] = function (event) { xodimTab('natija')
  };
  R["h183"] = function (event) { xodimTab('foto')
  };
  R["h184"] = function (event) { xodimTab('tarix')
  };
  R["h185"] = function (event) { xodimRenderBuyurtmalar()
  };
  R["h186"] = function (event) { xodimSubmitNatija(event)
  };
  R["h187"] = function (event) { xodimFotoPreview(this)
  };
  R["h188"] = function (event) { xodimSaveFoto()
  };
  R["h189"] = function (event) { xodimInvoicePreview(this)
  };
  R["h190"] = function (event) { xodimSaveInvoice()
  };
  R["h191"] = function (event) { qaytaYetkazishSora()
  };
  R["h192"] = function (event) { kuryerPanelYop()
  };
  R["h193"] = function (event) { kuryerRoyxatYukla(0)
  };
  R["h194"] = function (event) { kuryerRoyxatYukla(1)
  };
  R["h195"] = function (event) { kuryerAmal('qabul')
  };
  R["h196"] = function (event) { kuryerAmal('yolda')
  };
  R["h197"] = function (event) { kuryerAmal('yetkazildi')
  };
  R["h198"] = function (event) { kuryerMuammoOch()
  };
  R["h199"] = function (event) { kuryerMuammoYubor()
  };
  R["h200"] = function (event) { tolovniOch()
  };
  R["h201"] = function (event) { tolovUsulOch()
  };
  R["h202"] = function (event) { this.style.color='#ff8a00'
  };
  R["h203"] = function (event) { this.style.color='#8b7820'
  };
  R["h204"] = function (event) { this.style.background='rgba(220,50,50,0.15)';this.style.color='#ff6b6b';this.style.borderColor='rgba(220,50,50,0.4)'
  };
  R["h205"] = function (event) { this.style.background='rgba(31,72,135,0.04)';this.style.color='#6a5820';this.style.borderColor='rgba(120,170,235,0.15)'
  };
  R["h206"] = function (event) { closeModal();openHisobPage('narx')
  };
  R["h207"] = function (event) { closeModal();showToast('Servis so\'rovi yuborildi! 30 daqiqa ichida bog\'lanamiz.')
  };
  R["h208"] = function (event) { closeModal();showToast('Hisobot emailga yuborildi!')
  };
  R["h209"] = function (event) { closeModal();showToast('Buyurtmangiz qabul qilindi! Tez orada bog\'lanamiz.')
  };
  R["h210"] = function (event) { closeModal();clearCart();showToast('Buyurtmangiz yuborildi!')
  };
  R["h211"] = function (event) { closeModal();openBuyurtmaOyna()
  };
  R["h212"] = function (event) { texnikShartTanlov()
  };
  R["h213"] = function (event) { texnikLoyihaBolimi()
  };
  R["h214"] = function (event) { loyihaOddiyBolim('ruxsatnomalar')
  };
  R["h215"] = function (event) { loyihaOddiyBolim('ekspertiza')
  };
  R["h216"] = function (event) { loyihaOddiyBolim('modellashtirish')
  };
  R["h217"] = function (event) { loyihaHa()
  };
  R["h218"] = function (event) { loyihaManzilBolimi()
  };
  R["h219"] = function (event) { loyihaKorishBolimi()
  };
  R["h220"] = function (event) { loyihaTexnikShartBolimi()
  };
  R["h221"] = function (event) { loyihaYoq()
  };
  R["h222"] = function (event) { saveTexnikShart(event)
  };
  R["h223"] = function (event) { updateFileName(this, 'tsFileName')
  };
  R["h224"] = function (event) { saveManzil(event)
  };
  R["h225"] = function (event) { manzilLokatsiyaOl()
  };
  R["h226"] = function (event) { loyihaKorishOtpYubor(event)
  };
  R["h227"] = function (event) { loyihaKorishTasdiqla(event)
  };
  R["h228"] = function (event) { this.style.borderColor='rgba(110,165,230,0.75)';this.style.boxShadow='0 0 0 1px rgba(255,200,40,0.18),0 12px 40px rgba(120,170,235,0.22),inset 0 1px 0 rgba(255,230,100,0.1)';this.style.transform='translateY(-4px)'
  };
  R["h229"] = function (event) { this.style.borderColor='rgba(120,170,235,0.28)';this.style.boxShadow='0 4px 24px rgba(0,0,0,0.7),inset 0 1px 0 rgba(255,220,80,0.06)';this.style.transform='translateY(0)'
  };
  R["h230"] = function (event) { this.style.background='rgba(120,170,235,0.2)';this.style.color='#ff8a00';this.style.borderColor='rgba(120,170,235,0.6)'
  };
  R["h231"] = function (event) { this.style.background='rgba(120,170,235,0.1)';this.style.color='#c8a830';this.style.borderColor='rgba(120,170,235,0.28)'
  };
  R["h232"] = function (event) { this.style.background='rgba(120,170,235,0.12)';this.style.color='#ff8a00'
  };
  R["h233"] = function (event) { this.style.background='transparent';this.style.color='#8b7820'
  };
  R["h234"] = function (event) { this.style.boxShadow='0 4px 24px rgba(110,165,230,0.5),inset 0 1px 0 rgba(255,255,255,0.2)';this.style.transform='scale(1.02)'
  };
  R["h235"] = function (event) { this.style.boxShadow='0 2px 16px rgba(120,170,235,0.3),inset 0 1px 0 rgba(255,255,255,0.15)';this.style.transform='scale(1)'
  };
  R["h236"] = function (event) { this.style.transform='scale(1.07)'
  };
  R["h237"] = function (event) { this.style.transform='scale(1)'
  };
  R["h238"] = function (event) { this.style.display='none';this.nextElementSibling.style.display='flex'
  };
  R["h239"] = function (event) { return false
  };
  R["h240"] = function (event) { katSwipeStart(event)
  };
  R["h241"] = function (event) { katSwipeEnd(event)
  };
  R["h242"] = function (event) { this.style.boxShadow='0 6px 20px rgba(34,158,217,0.45)';this.style.transform='translateY(-1px)'
  };
  R["h243"] = function (event) { this.style.boxShadow='0 4px 14px rgba(34,158,217,0.3)';this.style.transform='translateY(0)'
  };
  R["h244"] = function (event) { katQty(-1)
  };
  R["h245"] = function (event) { katQty(1)
  };
  R["h246"] = function (event) { katSavatga()
  };
  R["h247"] = function (event) { katSorovSend(event)
  };
  R["h248"] = function (event) { katResultClose()
  };
  R["h249"] = function (event) { katResultClose();katInfoClose();closeKatPage();openCartPage()
  };
  R["h250"] = function (event) { qdSlaydSurish(-1)
  };
  R["h251"] = function (event) { qdSlaydSurish(1)
  };
  R["h252"] = function (event) { narxnomaYukla()
  };
  R["h253"] = function (event) { closeModal();document.querySelector('#aloqa').scrollIntoView({behavior:'smooth'})
  };
  R["c:bolibOy"] = function (e) { bolibOy.apply(null, SG_ARGS(this, e)); };
  R["c:cartRemove"] = function (e) { cartRemove.apply(null, SG_ARGS(this, e)); };
  R["c:cartSetQty"] = function (e) { cartSetQty.apply(null, SG_ARGS(this, e)); };
  R["c:grlInfo"] = function (e) { grlInfo.apply(null, SG_ARGS(this, e)); };
  R["c:grlQty"] = function (e) { grlQty.apply(null, SG_ARGS(this, e)); };
  R["c:grlQtyInput"] = function (e) { grlQtyInput.apply(null, SG_ARGS(this, e)); };
  R["c:katHujjatOch"] = function (e) { katHujjatOch.apply(null, SG_ARGS(this, e)); };
  R["c:katInfo"] = function (e) { katInfo.apply(null, SG_ARGS(this, e)); };
  R["c:katSlideGoto"] = function (e) { katSlideGoto.apply(null, SG_ARGS(this, e)); };
  R["c:katSlideMove"] = function (e) { katSlideMove.apply(null, SG_ARGS(this, e)); };
  R["c:kuryerBuyurtmaOch"] = function (e) { kuryerBuyurtmaOch.apply(null, SG_ARGS(this, e)); };
  R["c:kuryerMuammoTanla"] = function (e) { kuryerMuammoTanla.apply(null, SG_ARGS(this, e)); };
  R["c:kuryerUlash"] = function (e) { kuryerUlash.apply(null, SG_ARGS(this, e)); };
  R["c:loyihaOddiyAriza"] = function (e) { loyihaOddiyAriza.apply(null, SG_ARGS(this, e)); };
  R["c:manzilOchir"] = function (e) { manzilOchir.apply(null, SG_ARGS(this, e)); };
  R["c:manzilTanla"] = function (e) { manzilTanla.apply(null, SG_ARGS(this, e)); };
  R["c:qdSlaydKorsat"] = function (e) { qdSlaydKorsat.apply(null, SG_ARGS(this, e)); };
  R["c:tolovUsulTanla"] = function (e) { tolovUsulTanla.apply(null, SG_ARGS(this, e)); };
  R["c:xaridBosqich"] = function (e) { xaridBosqich.apply(null, SG_ARGS(this, e)); };
  R["c:xodimAccept"] = function (e) { xodimAccept.apply(null, SG_ARGS(this, e)); };
  R["c:xodimStartWork"] = function (e) { xodimStartWork.apply(null, SG_ARGS(this, e)); };
  R["c:xzTab"] = function (e) { xzTab.apply(null, SG_ARGS(this, e)); };
  R['sty'] = function (e) { var o = SG_ARGS(this, e)[0] || {}; for (var k in o) this.style[k] = o[k]; };
  R["c:xaridNatijaKorsat"] = function (e) { xaridNatijaKorsat.apply(null, SG_ARGS(this, e)); };
  R["c:grlOrder"] = function (e) { grlOrder.apply(null, SG_ARGS(this, e)); };
  R["c:narxnomaTarmoq"] = function (e) { narxnomaTarmoq.apply(null, SG_ARGS(this, e)); };
  R["c:metroBolimOch"] = function (e) { metroBolimOch.apply(null, SG_ARGS(this, e)); };
  R["c:metroOynaYopArizaga"] = function (e) { metroOynaYop(); metroArizaga.apply(null, SG_ARGS(this, e)); };
})();
