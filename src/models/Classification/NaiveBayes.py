from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import confusion_matrix, accuracy_score


class NaiveBayesModel:
    def __init__(self, data_X, data_y):
        self.X_train, self.X_test, self.y_train, self.y_test = \
            train_test_split(data_X, data_y, test_size=0.25, random_state=0)

        self.sc = StandardScaler()
        self.X_train = self.sc.fit_transform(self.X_train)
        self.X_test = self.sc.transform(self.X_test)

        self.classifier = GaussianNB()
        self.classifier.fit(self.X_train, self.y_train)

        self.y_pred = self.classifier.predict(self.X_test)

        cm = confusion_matrix(self.y_test, self.y_pred)
        print("Naive Bayes:")
        print(cm)
        print(accuracy_score(self.y_test, self.y_pred))