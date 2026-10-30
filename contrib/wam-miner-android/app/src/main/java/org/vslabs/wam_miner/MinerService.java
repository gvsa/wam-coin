package org.vslabs.wam_miner;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Intent;
import android.os.Build;
import android.os.IBinder;
import androidx.annotation.Nullable;
import androidx.core.app.NotificationCompat;
import org.vslabs.model.MinerConfigModel;
import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

public class MinerService extends Service {
    private static final String CHANNEL_ID = "MinerServiceChannel";
    private static final int NOTIFICATION_ID = 1;

    // Action definitions for handling service control
    public static final String ACTION_START = "START_MINER";
    public static final String ACTION_STOP = "STOP_MINER";

    private Process minerProcess;
    private boolean isRunning = false;

    @Override
    public void onCreate() {
        super.onCreate();
        createNotificationChannel();
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && ACTION_STOP.equals(intent.getAction())) {
            // User clicked the quit action in the notification
            stopSelf();
            return START_NOT_STICKY;
        }

        if (!isRunning) {
            isRunning = true;
            MinerConfigModel config = (MinerConfigModel) intent.getSerializableExtra("CONFIG");

            // 1. Intent that calls back into this service with the STOP action
            Intent stopIntent = new Intent(this, MinerService.class);
            stopIntent.setAction(ACTION_STOP);

            // Flag handling for API 30+ compatibility (PendingIntent.FLAG_IMMUTABLE)
            int pendingFlags = Build.VERSION.SDK_INT >= Build.VERSION_CODES.M
                    ? PendingIntent.FLAG_IMMUTABLE : 0;

            PendingIntent stopPendingIntent = PendingIntent.getService(
                    this,
                    0,
                    stopIntent,
                    pendingFlags
            );

            // 2. Add the Action button to the Notification Builder
            Notification notification = new NotificationCompat.Builder(this, CHANNEL_ID)
                    .setContentTitle("Miner Running")
                    .setContentText("The background miner process is active.")
                    .setSmallIcon(android.R.drawable.ic_media_play)
                    .setPriority(NotificationCompat.PRIORITY_LOW)
                    .setOngoing(true) // Keeps notification from being swiped away
                    .addAction(android.R.drawable.ic_menu_close_clear_cancel, "Quit", stopPendingIntent)
                    .build();

            startForeground(NOTIFICATION_ID, notification);

            new Thread(() -> runMiner(config)).start();
        }

        return START_NOT_STICKY;
    }

    private void runMiner(MinerConfigModel config) {
        try {
            String nativeLibDir = this.getApplicationInfo().nativeLibraryDir;
            File binaryFile = new File(nativeLibDir, "libwam-miner.so");
            File libFile = new File(nativeLibDir, "libc++_shared.so");

            if (!binaryFile.exists()) return;

            List<String> args = new ArrayList<>();
            args.add(binaryFile.getAbsolutePath());
            args.add("-o");
            args.add(config.stratum + ":" + config.port);
            args.add("-u");

            if (config.name.trim().length() > 1) {
                config.address = config.address + "." + config.name;
            }
            args.add(config.address);
            args.add("-t");
            args.add(String.valueOf(config.cores));

            ProcessBuilder pb = new ProcessBuilder(args);
            pb.directory(getFilesDir());
            pb.redirectErrorStream(true);

            Map<String, String> env = pb.environment();
            env.put("LD_PRELOAD", libFile.getAbsolutePath());
            env.put("LD_LIBRARY_PATH", nativeLibDir);

            minerProcess = pb.start();

            BufferedReader reader = new BufferedReader(new InputStreamReader(minerProcess.getInputStream()));
            String line;
            while (isRunning && (line = reader.readLine()) != null) {
                Intent logIntent = new Intent("MINER_LOG_BROADCAST");
                logIntent.putExtra("LOG_LINE", line);
                sendBroadcast(logIntent);
            }
            reader.close();

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    private void createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            NotificationChannel serviceChannel = new NotificationChannel(
                    CHANNEL_ID,
                    "Miner Service Channel",
                    NotificationManager.IMPORTANCE_LOW
            );
            NotificationManager manager = getSystemService(NotificationManager.class);
            if (manager != null) {
                manager.createNotificationChannel(serviceChannel);
            }
        }
    }

    @Override
    public void onDestroy() {
        isRunning = false;
        if (minerProcess != null) {
            minerProcess.destroy(); // Safely terminates the underlying binary process
        }
        stopForeground(true); // Removes the notification element cleanly
        super.onDestroy();
    }

    @Nullable
    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
