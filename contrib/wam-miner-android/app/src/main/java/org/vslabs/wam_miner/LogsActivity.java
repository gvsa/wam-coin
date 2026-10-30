package org.vslabs.wam_miner;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.ViewGroup;
import android.widget.FrameLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import androidx.appcompat.app.AppCompatActivity;

import java.util.LinkedList;

public class LogsActivity extends AppCompatActivity {
    private static final String TAG = "WAM_APK_LOGS_UI";

    private TextView logTextView;
    private ScrollView scrollView;
    private boolean isReceiverRegistered = false;
    private final LinkedList<String> logLines = new LinkedList<>();

    // Intercepts the real-time reporting log strings sent by MinerNativeService
    private final BroadcastReceiver logReceiver = new BroadcastReceiver() {
        @Override
        public void onReceive(Context context, Intent intent) {
            if (intent != null && MinerNativeService.ACTION_NATIVE_LOG_BROADCAST.equals(intent.getAction())) {
                String logLine = intent.getStringExtra("LOG_LINE");
                if (logLine != null) {
                    logLines.add(logLine);

                    // Cap log cache at 150 lines to completely eliminate UI rendering lag
                    if (logLines.size() > 150) {
                        logLines.removeFirst();
                    }

                    StringBuilder displayBuffer = new StringBuilder();
                    for (String line : logLines) {
                        displayBuffer.append(line).append("\n");
                    }

                    logTextView.setText(displayBuffer.toString());
                    // Keep the console view pinned smoothly to the latest update line
                    scrollView.post(() -> scrollView.fullScroll(ScrollView.FOCUS_DOWN));
                }
            }
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        // Build the classic mining console terminal theme layout programmatically
        scrollView = new ScrollView(this);
        scrollView.setLayoutParams(new ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        scrollView.setBackgroundColor(0xFF121212); // Midnight Charcoal

        logTextView = new TextView(this);
        logTextView.setLayoutParams(new FrameLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT));
        logTextView.setPadding(40, 40, 40, 40);
        logTextView.setTextSize(13);
        logTextView.setTextColor(0xFF00FF00); // Matrix Green
        logTextView.setTypeface(android.graphics.Typeface.MONOSPACE); // Perfect table alignment

        scrollView.addView(logTextView);
        setContentView(scrollView);

        logTextView.setText("--- WAM NATIVE CONSOLE INTERFACE LINE ACTIVE ---\nInitializing mining cores. Waiting for pool job templates...\n");
    }

    @Override
    protected void onStart() {
        super.onStart();
        if (!isReceiverRegistered) {
            IntentFilter filter = new IntentFilter(MinerNativeService.ACTION_NATIVE_LOG_BROADCAST);
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                registerReceiver(logReceiver, filter, Context.RECEIVER_EXPORTED);
            } else {
                registerReceiver(logReceiver, filter);
            }
            isReceiverRegistered = true;
            Log.i(TAG, "Logs Activity attached cleanly to the global application broadcast bus.");
        }
    }

    @Override
    protected void onStop() {
        super.onStop();
        if (isReceiverRegistered) {
            try {
                unregisterReceiver(logReceiver);
            } catch (Exception e) {
                // Already cleared safely
            }
            isReceiverRegistered = false;
        }
    }

    // =======================================================================
    // STRICT LIFECYCLE BINDING: Exiting this screen terminates all operations
    // =======================================================================
    @Override
    protected void onDestroy() {
        Log.i(TAG, "Logs window closed by the operator. Sending absolute kill sequence to background service.");

        // 1. Fire explicit stop signal to halt C++ loop macros
        Intent stopIntent = new Intent(this, MinerNativeService.class);
        stopIntent.setAction(MinerNativeService.ACTION_STOP_NATIVE);
        startService(stopIntent);

        super.onDestroy();
    }
}
