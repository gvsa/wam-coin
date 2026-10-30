package org.vslabs.wam_miner;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Build;
import android.os.Bundle;
import android.widget.ScrollView;
import android.widget.TextView;
import androidx.appcompat.app.AppCompatActivity;
import org.vslabs.model.MinerConfigModel;
import java.util.LinkedList;

public class MinerActivity extends AppCompatActivity {
    private TextView logTextView;
    private ScrollView scrollView;
    private final LinkedList<String> logLines = new LinkedList<>();

    // Receiver to safely catch logs transmitted from the Foreground Service
    private final BroadcastReceiver logReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            String newLine = intent.getStringExtra("LOG_LINE");
            if (newLine != null) {
                logLines.add(newLine);
                if (logLines.size() > 100) {
                    logLines.removeFirst();
                }

                StringBuilder logDisplay = new StringBuilder();
                for (String log : logLines) {
                    logDisplay.append(log).append("\n");
                }
                updateLog(logDisplay.toString());
            }
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        MinerConfigModel config = (MinerConfigModel) this.getIntent().getSerializableExtra("CONFIG");

        scrollView = new ScrollView(this);
        logTextView = new TextView(this);
        logTextView.setPadding(30, 30, 30, 30);
        logTextView.setTextSize(14);
        scrollView.addView(logTextView);
        setContentView(scrollView);

        logTextView.setText("Starting miner background service...\n");

        // Fire up the Foreground service package
        Intent serviceIntent = new Intent(this, MinerService.class);
        serviceIntent.setAction(MinerService.ACTION_START);
        serviceIntent.putExtra("CONFIG", config);

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(serviceIntent);
        } else {
            startService(serviceIntent);
        }
    }

    @Override
    protected void onStart() {
        super.onStart();
        // Register the log listener when the UI comes into view
        registerReceiver(logReceiver, new IntentFilter("MINER_LOG_BROADCAST"), Context.RECEIVER_NOT_EXPORTED);
    }

    @Override
    protected void onStop() {
        super.onStop();
        // Unregister listener when UI is minimized so resources aren't wasted
        unregisterReceiver(logReceiver);
    }

    private void updateLog(final String text) {
        logTextView.setText(text);
        scrollView.fullScroll(ScrollView.FOCUS_DOWN);
    }

    // Optional: If you want the process to die when the user explicitly clears the activity, keep onDestroy
    @Override
    protected void onDestroy() {
        super.onDestroy();
        // Intent stopIntent = new Intent(this, MinerService.class);
        // stopService(stopIntent);
    }
}
