import os
import firebase_admin
from firebase_admin import credentials, messaging
from app import app, db, RemajaPutri

# --- Inisialisasi Firebase Admin SDK ---
cred_path = os.path.join(os.path.dirname(__file__), 'service-account-key.json')
cred = credentials.Certificate(cred_path)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)
# ----------------------------------------

def send_daily_reminders():
    print("Memulai pengiriman notifikasi pengingat harian...")
    
    with app.app_context():
        users_with_tokens = RemajaPutri.query.filter(RemajaPutri.fcm_token.isnot(None)).all()
        
        if not users_with_tokens:
            print("Tidak ada pengguna dengan token FCM. Proses selesai.")
            return

        tokens = [user.fcm_token for user in users_with_tokens]
        
        print(f"Menemukan {len(tokens)} token. Mencoba mengirim notifikasi...")

        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title='🔔 Pengingat Harian DSC!',
                body='Jangan lupa catat aktivitas minum Tablet Tambah Darah (TTD) hari ini ya, Semangat Sehat! 💪'
            ),
            tokens=tokens,
        )

        try:
            # Pastikan penulisan nama fungsi sudah benar:
            response = messaging.send_each_for_multicast(message)
            print(f'Total notifikasi yang dikirim: {len(response.responses)}')
            print(f'Berhasil: {response.success_count}, Gagal: {response.failure_count}')
            
            if response.failure_count > 0:
                for i, send_response in enumerate(response.responses):
                    if not send_response.success:
                        print(f'   Error pada token ke-{i+1}: {send_response.exception}')

        except Exception as e:
            print(f"Terjadi error saat mengirim notifikasi: {e}")

if __name__ == '__main__':
    send_daily_reminders()