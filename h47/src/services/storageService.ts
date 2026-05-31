import { openDB, IDBPDatabase } from 'idb';
import { ErrorRecord, ErrorStatistics, RecordedSession } from '@/types';

const DB_NAME = 'SignLanguageCorrector';
const DB_VERSION = 1;
const ERROR_RECORDS_STORE = 'errorRecords';
const SESSIONS_STORE = 'sessions';
const SETTINGS_STORE = 'userSettings';

export class StorageService {
  private dbPromise: Promise<IDBPDatabase> | null = null;

  private async getDB(): Promise<IDBPDatabase> {
    if (!this.dbPromise) {
      this.dbPromise = openDB(DB_NAME, DB_VERSION, {
        upgrade: (db) => {
          if (!db.objectStoreNames.contains(ERROR_RECORDS_STORE)) {
            const errorStore = db.createObjectStore(ERROR_RECORDS_STORE, { keyPath: 'id' });
            errorStore.createIndex('timestamp', 'timestamp', { unique: false });
          }

          if (!db.objectStoreNames.contains(SESSIONS_STORE)) {
            const sessionStore = db.createObjectStore(SESSIONS_STORE, { keyPath: 'id' });
            sessionStore.createIndex('timestamp', 'timestamp', { unique: false });
          }

          if (!db.objectStoreNames.contains(SETTINGS_STORE)) {
            db.createObjectStore(SETTINGS_STORE, { keyPath: 'key' });
          }
        },
      });
    }
    return this.dbPromise;
  }

  async saveErrorRecord(record: ErrorRecord): Promise<void> {
    const db = await this.getDB();
    await db.put(ERROR_RECORDS_STORE, record);
  }

  async getErrorRecords(limit: number = 100): Promise<ErrorRecord[]> {
    const db = await this.getDB();
    const records = await db.getAllFromIndex(
      ERROR_RECORDS_STORE,
      'timestamp',
      IDBKeyRange.lowerBound(0)
    );
    return records.sort((a, b) => b.timestamp - a.timestamp).slice(0, limit);
  }

  async getErrorRecordById(id: string): Promise<ErrorRecord | undefined> {
    const db = await this.getDB();
    return db.get(ERROR_RECORDS_STORE, id);
  }

  async deleteErrorRecord(id: string): Promise<void> {
    const db = await this.getDB();
    await db.delete(ERROR_RECORDS_STORE, id);
  }

  async getStatistics(): Promise<ErrorStatistics> {
    const records = await this.getErrorRecords(1000);
    const byType: Record<string, number> = {};
    const byWord: Record<string, number> = {};
    const trendMap: Record<string, number> = {};

    records.forEach(record => {
      record.errors.forEach(error => {
        byType[error.type] = (byType[error.type] || 0) + 1;
        byWord[error.word] = (byWord[error.word] || 0) + 1;
      });

      const date = new Date(record.timestamp).toISOString().split('T')[0];
      trendMap[date] = (trendMap[date] || 0) + 1;
    });

    const trend = Object.entries(trendMap)
      .map(([date, count]) => ({ date, count }))
      .sort((a, b) => a.date.localeCompare(b.date))
      .slice(-30);

    return {
      totalCount: records.length,
      byType,
      byWord,
      trend
    };
  }

  async clearErrorRecords(): Promise<void> {
    const db = await this.getDB();
    await db.clear(ERROR_RECORDS_STORE);
  }

  async exportData(): Promise<string> {
    const records = await this.getErrorRecords(10000);
    const statistics = await this.getStatistics();
    
    const exportData = {
      exportDate: new Date().toISOString(),
      records,
      statistics
    };

    return JSON.stringify(exportData, null, 2);
  }

  async downloadExport(): Promise<void> {
    const data = await this.exportData();
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sign-language-stats-${new Date().toISOString().split('T')[0]}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  async saveSession(session: RecordedSession): Promise<void> {
    const db = await this.getDB();
    const sessionToSave = {
      ...session,
      frames: session.frames.slice(-300)
    };
    await db.put(SESSIONS_STORE, sessionToSave);
  }

  async getSessions(limit: number = 20): Promise<RecordedSession[]> {
    const db = await this.getDB();
    const sessions = await db.getAllFromIndex(
      SESSIONS_STORE,
      'timestamp',
      IDBKeyRange.lowerBound(0)
    );
    return sessions.sort((a, b) => b.timestamp - a.timestamp).slice(0, limit);
  }

  async getSessionById(id: string): Promise<RecordedSession | undefined> {
    const db = await this.getDB();
    return db.get(SESSIONS_STORE, id);
  }

  async deleteSession(id: string): Promise<void> {
    const db = await this.getDB();
    await db.delete(SESSIONS_STORE, id);
  }

  async saveSetting(key: string, value: any): Promise<void> {
    const db = await this.getDB();
    await db.put(SETTINGS_STORE, { key, value });
    localStorage.setItem(key, JSON.stringify(value));
  }

  async getSetting<T = any>(key: string, defaultValue: T): Promise<T> {
    try {
      const localValue = localStorage.getItem(key);
      if (localValue !== null) {
        return JSON.parse(localValue);
      }

      const db = await this.getDB();
      const result = await db.get(SETTINGS_STORE, key);
      if (result) {
        return result.value;
      }
    } catch (e) {
      console.error('Error getting setting:', e);
    }
    return defaultValue;
  }

  async clearAll(): Promise<void> {
    const db = await this.getDB();
    const tx = db.transaction([ERROR_RECORDS_STORE, SESSIONS_STORE, SETTINGS_STORE], 'readwrite');
    await Promise.all([
      tx.objectStore(ERROR_RECORDS_STORE).clear(),
      tx.objectStore(SESSIONS_STORE).clear(),
      tx.objectStore(SETTINGS_STORE).clear(),
      tx.done
    ]);
    localStorage.clear();
  }

  async getTodayErrorCount(): Promise<number> {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const todayStart = today.getTime();

    const db = await this.getDB();
    const records = await db.getAllFromIndex(
      ERROR_RECORDS_STORE,
      'timestamp',
      IDBKeyRange.lowerBound(todayStart)
    );
    return records.length;
  }

  async getWeeklyErrorCount(): Promise<number> {
    const weekAgo = new Date();
    weekAgo.setDate(weekAgo.getDate() - 7);
    weekAgo.setHours(0, 0, 0, 0);
    const weekStart = weekAgo.getTime();

    const db = await this.getDB();
    const records = await db.getAllFromIndex(
      ERROR_RECORDS_STORE,
      'timestamp',
      IDBKeyRange.lowerBound(weekStart)
    );
    return records.length;
  }
}

export const storageService = new StorageService();
