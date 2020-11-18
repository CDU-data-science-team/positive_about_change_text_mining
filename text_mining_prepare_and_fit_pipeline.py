"""
================================================================================
Classification of patient feedback using algoritmhs that can efficiently
handle sparse matrices
================================================================================

Classify documents by label using a bag-of-words approach.

See example in https://scikit-learn.org/stable/auto_examples/text/plot_document_classification_20newsgroups.html?highlight=text%20classification%20sparse

"""

# https://scikit-learn.org/stable/tutorial/text_analytics/working_with_text_data.html
# https://scikit-learn.org/stable/modules/feature_extraction.html#feature-hashing

#############################################################################
# Define learners that can handle sparse matrices
# ------------------------------------
learners = [#XGBClassifier(),
            RidgeClassifier(),
            #LinearSVC(max_iter=10000), # I always run into convergence issue with this. Switch off permanently. See hermidalc's comment on 20 Apr 2020 on https://github.com/scikit-learn/scikit-learn/issues/11536
            SGDClassifier(max_iter=10000),
            Perceptron(),
            PassiveAggressiveClassifier(),
            BernoulliNB(),
            ComplementNB(),
            MultinomialNB(),
            KNeighborsClassifier(),
            NearestCentroid(),
            #RandomForestClassifier()
            ]

learners = [SGDClassifier(max_iter=10000)] # Uncomment this for quick & dirty experimentation

#############################################################################
# NLTK/spaCy-based function for lemmatizing
# ------------------------------------
# https://scikit-learn.org/stable/modules/feature_extraction.html?highlight=stemming
class LemmaTokenizer:
    def __init__(self, tknz='wordnet'):
        self.tknz = tknz
    def __call__(self, doc):
        if self.tknz == 'wordnet':
            wln = WordNetLemmatizer()
            return [wln.lemmatize(t) for t in word_tokenize(doc)]
        if self.tknz == 'spacy': 
            return [t.lemma_ for t in nlp(doc, 
                                          disable=["tagger", "parser", "ner"])]

#############################################################################
# Function for automating pipeline for > 1 learners
# ------------------------------------
# https://stackoverflow.com/questions/48507651/multiple-classification-models-in-a-scikit-pipeline-python
class ClfSwitcher(BaseEstimator):
    def __init__(
                 self,
                 estimator=SGDClassifier(max_iter=10000),
    ): self.estimator = estimator

    def fit(self, X, y=None, **kwargs):
        self.estimator.fit(X, y)
        return self

    def predict(self, X, y=None):
        return self.estimator.predict(X)

    def predict_proba(self, X):
        return self.estimator.predict_proba(X)

    def score(self, X, y):
        return self.estimator.score(X, y)

#############################################################################
# Prepare pipeline
# ------------------------------------
# Preprocess numerical and text data in different ways.
# Numerical data are min-max normalized because X^2 and Multinomial Naive 
# Bayes can't handle negative data. NOTE: FIND OUT IF IT IS METHODOLOGICALLY 
# SOUND TO DO THIS!
# Pipeline for numeric features
"""numeric_features = ['comment_polarity']
numeric_transformer = Pipeline(steps=[
    ('minmax', MinMaxScaler())])"""

# Pipeline for text features
text_features = 'improve' # Needs to be a scalar, otherwise TfidfVectorizer() throws an error
text_transformer = Pipeline(steps=[
    # Lemmatization with NLTK and spaCy returns similar results. Slightly 
    # better with spaCy, and also faster. Define spaCy as the lemmatizer here
    # and switch off preprocessor__text__tfidf__tokenizer in param grid below.
    #('tfidf', (TfidfVectorizer(tokenizer=LemmaTokenizer(tknz='spacy'), # https://kavita-ganesan.com/tfidftransformer-tfidfvectorizer-usage-differences/
    #                           stop_words='english')))]) # No easy way around stop word lists. For now, use Scikit's list in combination with max/min_df. See https://scikit-learn.org/stable/modules/feature_extraction.html#stop-words
    ('tfidf', (TfidfVectorizer(tokenizer=LemmaTokenizer(tknz='spacy'))))]) # https://kavita-ganesan.com/tfidftransformer-tfidfvectorizer-usage-differences/

# Pass both pipelines/preprocessors to a column transformer
preprocessor = ColumnTransformer(
    transformers=[
        #('num', numeric_transformer, numeric_features),
        ('text', text_transformer, text_features)])

# Pipeline with preprocessors, any other operations and a learner
pipe = Pipeline(steps=[('preprocessor', preprocessor),
                       #('kbest', SelectKBest(chi2)),
                       #('rfe', RFE(estimator=LogisticRegression(solver="sag", max_iter=10000), step=0.5)),
                       ('selectperc', SelectPercentile(chi2)),
                      ('clf', ClfSwitcher())])

# Parameter grid
"""# Let's first define a variable for the SelectKBest grid. We will be running
# a 5-fold CV, in which 4/5 (80%) of the data will be in the train set.
# We can then set k to be, say 50% of the 80% of the data.
kbest_number_of_features = len(X_train.index) * 4 / 5"""

param_grid_preproc = {
    'clf__estimator': None,
    'preprocessor__text__tfidf__ngram_range': ((1, 1), (2, 2), (1, 3)),
    # Lemmatization with NLTK and spaCy returns similar results. Slightly 
    # better with spaCy, and also faster. Remove from grid below.
    #'preprocessor__text__tfidf__tokenizer': [LemmaTokenizer(tknz='spacy'),
    #                                         LemmaTokenizer(tknz='wordnet')],
    'preprocessor__text__tfidf__max_df': [0.7, 0.95],
    'preprocessor__text__tfidf__min_df': [3, 1], # Value 1 is the default, which does nothing (i.e. keeps all terms)
    'preprocessor__text__tfidf__use_idf': [True, False],
    #'kbest__k': (1000, 'all'),
    'selectperc__percentile': [10, 50, 100],
    #'rfecv__estimator': [DecisionTreeClassifier()],
    #'rfecv__step': (0.1, 0.25, 0.5) # Has a scoring argument too. Investigate
}

param_grid = []
for i in learners:
    aux = param_grid_preproc.copy()
    aux['clf__estimator'] = [i]
    aux['preprocessor__text__tfidf__norm'] = ['l2'] # See long comment below
    if i.__class__.__name__ == LinearSVC().__class__.__name__:
        aux['clf__estimator__class_weight'] = [None, 'balanced']
        #aux['clf__estimator__dual'] = [True, False] # https://stackoverflow.com/questions/52670012/convergencewarning-liblinear-failed-to-converge-increase-the-number-of-iterati
    if i.__class__.__name__ == BernoulliNB().__class__.__name__:
        aux['clf__estimator__alpha'] = (0.1, 0.5, 1)
    if i.__class__.__name__ == ComplementNB().__class__.__name__:
        aux['clf__estimator__alpha'] = (0.1, 0.5, 1)
    if i.__class__.__name__ == MultinomialNB().__class__.__name__:
        aux['clf__estimator__alpha'] = (0.1, 0.5, 1)
    if i.__class__.__name__ == SGDClassifier().__class__.__name__: # Perhaps try out loss='log' at some point?
        aux['clf__estimator__class_weight'] = [None, 'balanced']
        aux['clf__estimator__penalty'] = ('l2', 'elasticnet')
    if i.__class__.__name__ == RidgeClassifier().__class__.__name__:
        aux['clf__estimator__class_weight'] = [None, 'balanced']
        aux['clf__estimator__alpha'] = (0.1, 1.0, 10.0)
    if i.__class__.__name__ == Perceptron().__class__.__name__:
        aux['clf__estimator__class_weight'] = [None, 'balanced']
        aux['clf__estimator__penalty'] = ('l2', 'elasticnet')
    if i.__class__.__name__ == RandomForestClassifier().__class__.__name__:
        aux['clf__estimator__max_features'] = ('sqrt', 0.666)
    param_grid.append(aux)
    # Use TfidfVectorizer() as CountVectorizer() also, to determine if raw
    # counts instead of frequencies improves perfomance. This requires 
    # use_idf=False and norm=None. We want to ensure that norm=None
    # will not be combined with use_idf=True inside the grid search, so we
    # create a separate parameter set to prevent this from happening. We do
    # this below with temp variable aux1.
    # Meanwhile, we want norm='l2' (the default) for the grid defined by temp
    # variable aux above. If we don't explicitly set norm='l2' in aux, the 
    # norm column in the table of the CV results (following fitting) is 
    # always emppty. My speculation is that Scikit-learn does consider norm
    # to be 'l2' for aux, but it doesn't print it. That's because unless we
    # explicitly run aux['preprocessor__text__tfidf__norm'] = ['l2'], setting
    # norm as 'l2' in aux is implicit (i.e. it's the default), while setting
    # norm as None in aux1 is explicit (i.e. done by the user). But we want
    # the colum norm in the CV results to clearly state which runs used the 
    # 'l2' norm, hence we explicitly run command 
    # aux['preprocessor__text__tfidf__norm'] = ['l2'] earlier on.
    aux1 = aux.copy()
    aux1['preprocessor__text__tfidf__use_idf'] = [False]
    aux1['preprocessor__text__tfidf__norm'] = [None]
    param_grid.append(aux1)
    

#############################################################################
# Benchmark classifiers
# ------------------------------------
# Set a scoring measure (other than accuracy) and train several 
# classification models.

# Matthews Correlation Coefficient as the scoring measure looks promising:
# https://towardsdatascience.com/the-best-classification-metric-youve-never-heard-of-the-matthews-correlation-coefficient-3bf50a2f3e9a
# https://towardsdatascience.com/matthews-correlation-coefficient-when-to-use-it-and-when-to-avoid-it-310b3c923f7e
# https://journals.plos.org/plosone/article/file?id=10.1371/journal.pone.0177678&type=printable
# Balanced accuracy too
# Class Balance Accuracy as well:
# https://lib.dr.iastate.edu/cgi/viewcontent.cgi?article=4544&context=etd

# Create Class Balance Accuracy scorer (p. 40 in PDF mentioned above)
def class_balance_accuracy_score(y_true, y_pred):
    cm = confusion_matrix(y_true, y_pred)
    c_i_dot = np.sum(cm, axis=1)
    c_dot_i = np.sum(cm, axis=0)
    cba = []
    for i in range(len(c_dot_i)):
        cba.append(cm[i][i] / max(c_i_dot[i], c_dot_i[i]))
    cba = sum(cba) / (i + 1)
    return cba

# Make sure that dictionary keys for '_score' metrics don't have the word
# 'score' oin them, e.g. key for accuracy_score() should be 'Accuracy', 
# not 'Accuracy Score'. Also, make sure each word is capitalized.
scoring = {'Accuracy': make_scorer(accuracy_score), 
           'Balanced Accuracy': make_scorer(balanced_accuracy_score),
           'Matthews Correlation Coefficient': make_scorer(matthews_corrcoef),
           'Class Balance Accuracy': make_scorer(class_balance_accuracy_score)}

# Grid search with 5-fold cross-validation
prompt_text = "We need a scorer based on which the pipeline will select \
the best learner. Enter the desired scorer, currently one of accuracy_score, \
balanced_accuracy_score, matthews_corrcoef or \
class_balance_accuracy_score:"
print(prompt_text)
# https://stackoverflow.com/questions/23294658/asking-the-user-for-input-until-they-give-a-valid-response
refit = input()
refit = refit.replace('_', ' ').replace(' score', '').title()

gscv = GridSearchCV(pipe, param_grid, n_jobs=5, return_train_score=False,
                    cv=5, verbose=3, 
                    scoring=scoring, refit=refit)
gscv.fit(X_train, y_train)

#############################################################################
# Save model to disk
# ------------------------------------
# https://machinelearningmastery.com/save-load-machine-learning-models-python-scikit-learn/
filename = 'finalized_model_4444.sav'
pickle.dump(gscv, open(filename, 'wb'))