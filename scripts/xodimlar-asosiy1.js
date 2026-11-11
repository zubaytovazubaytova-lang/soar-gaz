      if (location.protocol === 'file:') {
        document.getElementById('qaytishHavola').href = 'index.html';        // Boshqaruv havolasi vaqtincha yashirilgan — bo'lmasligi mumkin
        const bh = document.getElementById('boshqaruvHavola');
        if (bh) bh.href = 'admin.html';
      }
    
